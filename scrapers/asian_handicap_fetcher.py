#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
亚盘赔率爬虫 - 从 titan007 亚盘页面抓取澳门主盘口数据。

只抓取:
  - 澳门公司（按页面公司名称匹配，非 companyID）
  - 主盘口（忽略盘2/盘3/盘4）
  - 赛前数据（已开赛比赛取赛前最后盘口）
"""

from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.logger import get_logger
from scrapers.proxy_config import apply_proxy_to_session
from scrapers.url_config import get_url

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    BeautifulSoup = None  # type: ignore[assignment,misc]

# ---------------------------------------------------------------------------
# 盘口文本 → 数值映射
# ---------------------------------------------------------------------------
HANDICAP_TEXT_MAP: Dict[str, float] = {
    "平手": 0,
    "平手/半球": 0.25,
    "半球": 0.5,
    "半球/一球": 0.75,
    "一球": 1.0,
    "一球/球半": 1.25,
    "球半": 1.5,
    "球半/两球": 1.75,
    "两球": 2.0,
    "两球/两球半": 2.25,
    "两球半": 2.5,
    "两球半/三球": 2.75,
    "三球": 3.0,
}

# 我们系统内部的澳门 company_id（独立于亚盘页面的 companyID）
MACAU_INTERNAL_COMPANY_ID = 80

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
]

BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Referer": "https://vip.titan007.com/",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
}


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------
@dataclass
class AsianHandicapRecord:
    """单场比赛的亚盘数据。"""
    match_id: int
    company_name: str
    company_id: int

    initial_home_odds: Optional[float] = None
    initial_handicap_line: Optional[float] = None
    initial_away_odds: Optional[float] = None

    current_home_odds: Optional[float] = None
    current_handicap_line: Optional[float] = None
    current_away_odds: Optional[float] = None


# ---------------------------------------------------------------------------
# 盘口解析工具
# ---------------------------------------------------------------------------
def parse_handicap_text(text: str) -> Optional[float]:
    """解析盘口文本为数值。

    正数 = 主队受让（主弱，获得让球）
    负数 = 主队让球（主强，让出球数）
    """
    text = text.strip()
    if not text or text == "-":
        return None

    if text.startswith("受让"):
        line_text = text[2:]
        base = HANDICAP_TEXT_MAP.get(line_text)
        return +base if base is not None else None

    if text.startswith("让"):
        line_text = text[1:]
        base = HANDICAP_TEXT_MAP.get(line_text)
        return -base if base is not None else None

    if text in HANDICAP_TEXT_MAP:
        base = HANDICAP_TEXT_MAP[text]
        # 裸文本无前缀且非平手 → 默认主让（负数）
        # titan007页面惯例: "半球/一球"=主让, "受让半球/一球"=主受让
        return -base if base != 0 else 0

    return None


def _safe_float(val: Optional[str]) -> Optional[float]:
    if val is None:
        return None
    val = val.strip()
    if not val or val == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 速率限制
# ---------------------------------------------------------------------------
class _RateLimiter:
    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = Lock()

    def wait(self):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


# ---------------------------------------------------------------------------
# 核心爬虫
# ---------------------------------------------------------------------------
class AsianHandicapFetcher:
    """从 titan007 亚盘页面抓取澳门主盘口（初盘+即时盘）。"""

    def __init__(
        self,
        delay: float = 0.5,
        workers: int = 3,
        max_retries: int = 3,
        timeout: int = 15,
    ) -> None:
        if requests is None:
            raise RuntimeError("Missing dependency 'requests'.")
        if BeautifulSoup is None:
            raise RuntimeError("Missing dependency 'beautifulsoup4'.")

        self.workers = workers
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)

        rps = 1.0 / delay if delay > 0 else 2.0
        self.rate_limiter = _RateLimiter(rps)

        self._sessions = [self._create_session() for _ in range(workers)]
        self._session_lock = Lock()

    # ---- session 管理 ----

    def _create_session(self) -> "requests.Session":
        session = requests.Session()
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        headers = dict(BROWSER_HEADERS)
        headers["User-Agent"] = random.choice(USER_AGENTS)
        session.headers.update(headers)
        apply_proxy_to_session(session)
        return session

    def _get_session(self) -> "requests.Session":
        with self._session_lock:
            return random.choice(self._sessions)

    # ---- 编码处理 ----

    @staticmethod
    def _decode_response(response: "requests.Response") -> str:
        if response.encoding and response.encoding.lower() not in ("iso-8859-1", "latin-1"):
            return response.text
        raw = response.content
        for enc in ("utf-8", "gb18030", "gb2312", "gbk"):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        return raw.decode("utf-8", errors="ignore")

    # ---- HTML 解析核心 ----

    def _parse_macau_main_line(self, match_id: int, html: str) -> Optional[AsianHandicapRecord]:
        """解析页面，提取澳门主盘口的初盘和终盘（即时盘）数据。"""
        soup = BeautifulSoup(html, "html.parser")

        # 1) 在主表格中找到澳门所在行
        macau_tr = self._find_macau_row(soup)
        if macau_tr is None:
            self.logger.debug("Match %s: 未找到澳门数据行", match_id)
            return None

        # 2) 从主表格行提取初盘和终盘
        initial = self._extract_opening_odds(macau_tr)
        current = self._extract_current_odds(macau_tr)

        if initial is None and current is None:
            self.logger.debug("Match %s: 澳门行存在但无法解析盘口数据", match_id)
            return None

        record = AsianHandicapRecord(
            match_id=match_id,
            company_name="澳门",
            company_id=MACAU_INTERNAL_COMPANY_ID,
        )

        if initial:
            record.initial_home_odds = initial[0]
            record.initial_handicap_line = initial[1]
            record.initial_away_odds = initial[2]

        if current:
            record.current_home_odds = current[0]
            record.current_handicap_line = current[1]
            record.current_away_odds = current[2]

        # 3) 如果比赛已开赛，从底部走势覆盖 current 为赛前最后盘口
        prematch_last = self._find_prematch_last_from_history(soup)
        if prematch_last is not None:
            record.current_home_odds = prematch_last[0]
            record.current_handicap_line = prematch_last[1]
            record.current_away_odds = prematch_last[2]

        return record

    def _find_macau_row(self, soup: "BeautifulSoup") -> Optional["Tag"]:
        """在亚盘表格中定位澳门的主盘口行（跳过盘2/盘3/盘4）。

        公司名可能在 td[0] 或 td[1]（页面结构中 td[0] 有时是空的勾选框列）。
        """
        for tr in soup.find_all("tr"):
            bgcolor = tr.get("bgcolor")
            if not bgcolor:
                continue
            cls = tr.get("class") or []
            if any("blue_txt" in c for c in cls):
                continue
            tds = tr.find_all("td")
            if len(tds) < 8:
                continue
            for td in tds[:3]:
                if "澳" in td.get_text(strip=True):
                    return tr
        return None

    def _extract_opening_odds(self, tr: "Tag") -> Optional[Tuple[float, float, float]]:
        """从一行中提取初盘数据: (home_odds, handicap_line, away_odds)。

        初盘 td 通过 title 属性识别，且不带 oddstype 属性。
        """
        tds = tr.find_all("td")
        open_cells = []
        for td in tds:
            if td.has_attr("title") and not td.has_attr("oddstype"):
                style = td.get("style", "")
                if "display" in style and "none" in style:
                    continue
                open_cells.append(td)
            if len(open_cells) >= 3:
                break

        if len(open_cells) < 3:
            return None

        home_odds = _safe_float(open_cells[0].get_text(strip=True))
        handicap_text = open_cells[1].get_text(strip=True)
        away_odds = _safe_float(open_cells[2].get_text(strip=True))
        handicap_line = parse_handicap_text(handicap_text)

        if home_odds is None or handicap_line is None or away_odds is None:
            return None
        return (home_odds, handicap_line, away_odds)

    def _extract_current_odds(self, tr: "Tag") -> Optional[Tuple[float, float, float]]:
        """从一行中提取终盘/即时盘数据。

        优先取 oddstype='wholeLastOdds'（赛前终盘），
        否则取 oddstype='wholeOdds'（即时盘）。
        """
        last_cells: list = []
        cur_cells: list = []
        for td in tr.find_all("td"):
            ost = td.get("oddstype")
            style = td.get("style", "")
            hidden = "display" in style and "none" in style
            if ost == "wholeLastOdds" and not hidden:
                last_cells.append(td)
            elif ost == "wholeOdds" and not hidden:
                cur_cells.append(td)

        cells = last_cells if len(last_cells) >= 3 else cur_cells
        if len(cells) < 3:
            return None

        home_odds = _safe_float(cells[0].get_text(strip=True))
        handicap_text = cells[1].get_text(strip=True)
        away_odds = _safe_float(cells[2].get_text(strip=True))
        handicap_line = parse_handicap_text(handicap_text)

        if home_odds is None or handicap_line is None or away_odds is None:
            return None
        return (home_odds, handicap_line, away_odds)

    def _find_prematch_last_from_history(self, soup: "BeautifulSoup") -> Optional[Tuple[float, float, float]]:
        """从底部历史走势表中，找到赛前最后一条澳门盘口。

        走势表每行格式: 盘口文本 水位1 水位2 | 比分 | 变化时间
        有比分的行 = 滚球期间 → 丢弃。
        如果找不到任何滚球行，说明比赛未开赛，返回 None（使用表格终盘即可）。
        """
        # 走势表通常在底部，包含大量行，每行有 "比分" 和 "变化时间" 列
        # 格式: td[0]=澳门列(盘口+水位), ... td[-2]=比分, td[-1]=变化时间
        # 寻找走势区域的特征: 行内有类似 "0-0", "1-2" 的比分文本
        history_rows = self._collect_history_rows(soup)
        if not history_rows:
            return None

        has_live_data = False
        last_prematch: Optional[Tuple[float, float, float]] = None

        for row_text, row_data in history_rows:
            if row_data is None:
                continue
            # 检测是否有比分（滚球）
            if self._is_live_row(row_text):
                has_live_data = True
            else:
                last_prematch = row_data

        if not has_live_data:
            return None

        return last_prematch

    def _collect_history_rows(self, soup: "BeautifulSoup") -> List[Tuple[str, Optional[Tuple[float, float, float]]]]:
        """收集底部走势表中澳门列的数据。

        返回 [(raw_row_text, (home_odds, handicap_line, away_odds) or None), ...]
        按页面顺序排列（早→晚）。
        """
        results: List[Tuple[str, Optional[Tuple[float, float, float]]]] = []

        # 走势区域在页面底部的 table 中，行内容特征: 含盘口文本 + 两个小数 + 比分 + 时间
        score_pattern = re.compile(r"^\d+-\d+$")
        handicap_pattern = re.compile(r"(受让|让)?(平手|半球|一球|球半|两球|两球半|三球)")

        all_trs = soup.find_all("tr")
        for tr in all_trs:
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue

            row_text = tr.get_text(separator=" ", strip=True)

            # 走势行的识别: 含盘口关键词 + 时间格式 (如 "2-19 04:00")
            if not handicap_pattern.search(row_text):
                continue
            time_match = re.search(r"\d{1,2}-\d{1,2}\s+\d{2}:\d{2}", row_text)
            if not time_match:
                continue

            # 提取第一列（澳门）的盘口数据
            first_td_text = tds[0].get_text(strip=True)
            parsed = self._parse_history_cell(first_td_text)
            results.append((row_text, parsed))

        return results

    def _parse_history_cell(self, cell_text: str) -> Optional[Tuple[float, float, float]]:
        """解析走势表中澳门列的单元格: '受让球半 0.98 0.86' → (0.98, +1.5, 0.86)。"""
        cell_text = cell_text.strip()
        if not cell_text:
            return None

        handicap_match = re.match(r"(受让|让)?(平手(?:/半球)?|半球(?:/一球)?|一球(?:/球半)?|球半(?:/两球)?|两球(?:/两球半)?|两球半(?:/三球)?|三球|平手)", cell_text)
        if not handicap_match:
            return None

        full_handicap_text = handicap_match.group(0)
        remainder = cell_text[handicap_match.end():].strip()

        handicap_line = parse_handicap_text(full_handicap_text)
        if handicap_line is None:
            return None

        nums = re.findall(r"\d+\.\d+", remainder)
        if len(nums) < 2:
            return None

        home_odds = _safe_float(nums[0])
        away_odds = _safe_float(nums[1])
        if home_odds is None or away_odds is None:
            return None

        return (home_odds, handicap_line, away_odds)

    @staticmethod
    def _is_live_row(row_text: str) -> bool:
        """判断走势行是否为滚球（已开赛）数据。

        比分格式 'N-N' (如 0-0, 1-2) vs 日期格式 'M-DD HH:MM' (如 2-19 04:07):
        用词边界 \\b 防止回溯拆分，用负向前瞻排除日期。
        """
        return bool(re.search(r"\b\d{1,2}-\d{1,2}\b(?!\s+\d{2}:\d{2})", row_text))

    # ---- 网络请求 ----

    def _fetch_single(self, match_id: int) -> Tuple[bool, Optional[AsianHandicapRecord], Optional[str]]:
        """抓取单场比赛的亚盘数据。返回 (success, record_or_None, error_or_None)。"""
        session = self._get_session()
        url = get_url("asian_handicap", match_id=match_id)

        for attempt in range(self.max_retries + 1):
            try:
                self.rate_limiter.wait()
                response = session.get(url, timeout=self.timeout, allow_redirects=True)

                if response.status_code == 403:
                    self.logger.warning("Match %s: 403 Forbidden (attempt %d)", match_id, attempt + 1)
                    session.headers["User-Agent"] = random.choice(USER_AGENTS)
                    time.sleep(2 ** attempt)
                    continue

                if response.status_code == 429:
                    self.logger.warning("Match %s: 429 Too Many Requests", match_id)
                    time.sleep(5 * (2 ** attempt))
                    continue

                if response.status_code == 404:
                    return False, None, f"404 Not Found"

                if not response.ok:
                    time.sleep(2 ** attempt)
                    continue

                html = self._decode_response(response)
                if len(html) < 200:
                    return False, None, "Response too short"

                record = self._parse_macau_main_line(match_id, html)
                if record is None:
                    return True, None, "No Macau data found"

                return True, record, None

            except requests.exceptions.Timeout:
                self.logger.warning("Match %s: timeout (attempt %d)", match_id, attempt + 1)
                time.sleep(2 ** attempt)
            except requests.exceptions.ConnectionError as e:
                self.logger.warning("Match %s: connection error (attempt %d): %s", match_id, attempt + 1, e)
                time.sleep(2 ** attempt)
            except Exception as e:
                self.logger.error("Match %s: unexpected error: %s", match_id, e, exc_info=True)
                return False, None, str(e)

        return False, None, f"Failed after {self.max_retries + 1} attempts"

    # ---- 批量入口 ----

    def fetch(self, match_ids: List[int]) -> List[AsianHandicapRecord]:
        """批量抓取多场比赛的亚盘数据。"""
        if not match_ids:
            return []

        records: List[AsianHandicapRecord] = []
        failed: List[int] = []
        no_data: List[int] = []

        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {
                    executor.submit(self._fetch_single, mid): mid
                    for mid in match_ids
                }
                for future in as_completed(futures):
                    mid = futures[future]
                    try:
                        success, record, error = future.result()
                        if record is not None:
                            records.append(record)
                        elif success:
                            no_data.append(mid)
                        else:
                            failed.append(mid)
                            if error:
                                self.logger.error("Match %s: %s", mid, error)
                    except Exception as e:
                        failed.append(mid)
                        self.logger.error("Match %s: future exception: %s", mid, e, exc_info=True)
        else:
            for mid in match_ids:
                success, record, error = self._fetch_single(mid)
                if record is not None:
                    records.append(record)
                elif success:
                    no_data.append(mid)
                else:
                    failed.append(mid)

        total = len(match_ids)
        self.logger.info(
            "亚盘爬取完成: %d/%d 成功, %d 无澳门数据, %d 失败, 获得 %d 条记录",
            total - len(failed) - len(no_data), total, len(no_data), len(failed), len(records),
        )
        if failed:
            self.logger.warning("失败的比赛: %s", ", ".join(str(m) for m in failed[:20]))

        return records

    # ---- 资源清理 ----

    def close(self) -> None:
        if hasattr(self, "_sessions"):
            for s in self._sessions:
                try:
                    s.close()
                except Exception:
                    pass
            self._sessions.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
