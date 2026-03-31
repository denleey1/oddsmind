#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
威廉欧赔历史变化爬虫

独立模块，从 Titan007 OddsHistory 页面获取威廉希尔的完整赔率变化时间线。
不改动任何现有爬虫或表结构。

流程:
  1. 请求 1x2d.titan007.com/{match_id}.js 提取 odds_id (JS数据的 parts[1])
  2. 请求 op1.titan007.com/OddsHistory.aspx?id={odds_id}&sid={match_id}&cid={cid}&l=0
  3. 解析 HTML 表格获取所有变化行
  4. 写入 william_odds_history 表
"""

from __future__ import annotations

import re
import time
import random
from datetime import datetime
from decimal import Decimal
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.logger import get_logger

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

logger = get_logger(__name__)

WILLIAM_CID = 115

JS_URL_TEMPLATE = "https://1x2d.titan007.com/{match_id}.js"
HISTORY_URL_TEMPLATE = (
    "https://op1.titan007.com/OddsHistory.aspx"
    "?id={odds_id}&sid={match_id}&cid={cid}&l=0"
)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]


class _RateLimiter:
    def __init__(self, rps: float = 2.0):
        self._interval = 1.0 / rps
        self._last = 0.0
        self._lock = Lock()

    def wait(self):
        with self._lock:
            now = time.time()
            gap = self._interval - (now - self._last)
            if gap > 0:
                time.sleep(gap)
            self._last = time.time()


class OddsHistoryScraper:
    """威廉欧赔历史变化爬虫"""

    def __init__(
        self,
        company_id: int = WILLIAM_CID,
        delay: float = 0.6,
        workers: int = 2,
        max_retries: int = 3,
        timeout: int = 15,
    ):
        self.company_id = company_id
        self.workers = workers
        self.max_retries = max_retries
        self.timeout = timeout
        self._limiter = _RateLimiter(1.0 / delay if delay > 0 else 2.0)
        self._session = self._build_session()

    def _build_session(self) -> requests.Session:
        s = requests.Session()
        retry = Retry(total=self.max_retries, backoff_factor=1,
                      status_forcelist=[429, 500, 502, 503, 504],
                      allowed_methods=["GET"])
        s.mount("https://", HTTPAdapter(max_retries=retry, pool_maxsize=10))
        s.mount("http://", HTTPAdapter(max_retries=retry, pool_maxsize=10))
        s.headers.update({
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        })
        try:
            from scrapers.proxy_config import apply_proxy_to_session
            apply_proxy_to_session(s)
        except Exception:
            pass
        return s

    # ------------------------------------------------------------------
    #  Step 1: 从 JS 获取 odds_id
    # ------------------------------------------------------------------
    def fetch_odds_id(self, match_id: int) -> Optional[str]:
        url = JS_URL_TEMPLATE.format(match_id=match_id)
        self._limiter.wait()
        try:
            resp = self._session.get(url, timeout=self.timeout)
            if not resp.ok:
                logger.warning(f"Match {match_id}: JS请求失败 HTTP {resp.status_code}")
                return None
            content = resp.content.decode("utf-8", errors="ignore")
            m = re.search(r"var game=Array\((.*?)\);", content, re.DOTALL)
            if not m:
                return None
            for rec in re.findall(r'"(.*?)"', m.group(1)):
                parts = rec.split("|")
                if len(parts) >= 2 and parts[0] == str(self.company_id):
                    return parts[1]
        except Exception as e:
            logger.error(f"Match {match_id}: 获取odds_id异常 - {e}")
        return None

    # ------------------------------------------------------------------
    #  Step 2: 获取并解析历史页面
    # ------------------------------------------------------------------
    def fetch_history(
        self, match_id: int, odds_id: str,
    ) -> List[Dict[str, Any]]:
        url = HISTORY_URL_TEMPLATE.format(
            odds_id=odds_id, match_id=match_id, cid=self.company_id,
        )
        self._limiter.wait()
        try:
            self._session.headers["User-Agent"] = random.choice(USER_AGENTS)
            resp = self._session.get(url, timeout=self.timeout)
            if not resp.ok:
                logger.warning(f"Match {match_id}: 历史页面 HTTP {resp.status_code}")
                return []
            html = resp.content.decode("utf-8", errors="ignore")
            return self._parse_history_html(match_id, html)
        except Exception as e:
            logger.error(f"Match {match_id}: 历史页面异常 - {e}")
            return []

    def _parse_history_html(
        self, match_id: int, html: str,
    ) -> List[Dict[str, Any]]:
        soup = BeautifulSoup(html, "html.parser")
        tbl = soup.find("table")
        if not tbl:
            return []

        rows = tbl.find_all("tr")
        if len(rows) < 2:
            return []

        results: List[Dict[str, Any]] = []
        now = datetime.now()
        current_year = now.year

        for tr in rows[1:]:
            tds = tr.find_all("td")
            if len(tds) < 11:
                continue
            texts = [td.get_text(strip=True) for td in tds]

            is_opening = "(初盘)" in texts[10]
            raw_time = texts[10].replace("(初盘)", "").strip()
            change_dt = self._parse_change_time(raw_time, current_year, now)

            results.append({
                "match_id": match_id,
                "company_id": self.company_id,
                "home_odds": _dec(texts[0]),
                "draw_odds": _dec(texts[1]),
                "away_odds": _dec(texts[2]),
                "home_prob": _pct(texts[3]),
                "draw_prob": _pct(texts[4]),
                "away_prob": _pct(texts[5]),
                "return_rate": _pct(texts[6]),
                "kelly_home": _dec(texts[7]),
                "kelly_draw": _dec(texts[8]),
                "kelly_away": _dec(texts[9]),
                "change_time": change_dt,
                "is_opening": 1 if is_opening else 0,
            })

        return results

    @staticmethod
    def _parse_change_time(raw: str, year: int, ref: datetime) -> Optional[datetime]:
        """解析 '03-25 13:44' 格式的变化时间，自动推断年份。"""
        try:
            dt = datetime.strptime(f"{year}-{raw}", "%Y-%m-%d %H:%M")
            if dt > ref:
                dt = dt.replace(year=year - 1)
            return dt
        except ValueError:
            return None

    # ------------------------------------------------------------------
    #  单场完整流程
    # ------------------------------------------------------------------
    def scrape_match(self, match_id: int) -> List[Dict[str, Any]]:
        odds_id = self.fetch_odds_id(match_id)
        if not odds_id:
            logger.debug(f"Match {match_id}: 未找到 cid={self.company_id} 的 odds_id")
            return []
        records = self.fetch_history(match_id, odds_id)
        logger.info(f"Match {match_id}: 获取 {len(records)} 条变化记录")
        return records

    # ------------------------------------------------------------------
    #  批量
    # ------------------------------------------------------------------
    def scrape_batch(self, match_ids: List[int]) -> List[Dict[str, Any]]:
        all_records: List[Dict[str, Any]] = []
        failed = 0
        for mid in match_ids:
            try:
                recs = self.scrape_match(mid)
                all_records.extend(recs)
            except Exception as e:
                failed += 1
                logger.error(f"Match {mid}: 批量爬取异常 - {e}")
        logger.info(
            f"批量完成: {len(match_ids)} 场, "
            f"成功 {len(match_ids) - failed}, "
            f"共 {len(all_records)} 条记录"
        )
        return all_records

    # ------------------------------------------------------------------
    #  存储
    # ------------------------------------------------------------------
    @staticmethod
    def save_to_db(records: List[Dict[str, Any]], db: Any) -> int:
        """批量写入 william_odds_history 表，返回实际插入/更新行数。"""
        if not records:
            return 0

        sql = """
            INSERT INTO william_odds_history
                (match_id, company_id, home_odds, draw_odds, away_odds,
                 home_prob, draw_prob, away_prob, return_rate,
                 kelly_home, kelly_draw, kelly_away,
                 change_time, is_opening)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON DUPLICATE KEY UPDATE
                home_odds  = VALUES(home_odds),
                draw_odds  = VALUES(draw_odds),
                away_odds  = VALUES(away_odds),
                home_prob  = VALUES(home_prob),
                draw_prob  = VALUES(draw_prob),
                away_prob  = VALUES(away_prob),
                return_rate= VALUES(return_rate),
                kelly_home = VALUES(kelly_home),
                kelly_draw = VALUES(kelly_draw),
                kelly_away = VALUES(kelly_away),
                is_opening = VALUES(is_opening)
        """
        rows_affected = 0
        for rec in records:
            try:
                ct = rec.get("change_time")
                if ct is None:
                    continue
                db.execute_query(sql, (
                    rec["match_id"], rec["company_id"],
                    rec["home_odds"], rec["draw_odds"], rec["away_odds"],
                    rec["home_prob"], rec["draw_prob"], rec["away_prob"],
                    rec["return_rate"],
                    rec["kelly_home"], rec["kelly_draw"], rec["kelly_away"],
                    ct, rec["is_opening"],
                ))
                rows_affected += 1
            except Exception as e:
                logger.error(f"写入失败 match={rec.get('match_id')}: {e}")
        return rows_affected

    def close(self):
        if hasattr(self, "_session"):
            self._session.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


# ------------------------------------------------------------------
#  辅助
# ------------------------------------------------------------------

def _dec(s: str) -> Optional[Decimal]:
    try:
        return Decimal(s.strip())
    except Exception:
        return None


def _pct(s: str) -> Optional[Decimal]:
    """解析 '73.21%' → 73.21"""
    try:
        return Decimal(s.strip().rstrip("%"))
    except Exception:
        return None
