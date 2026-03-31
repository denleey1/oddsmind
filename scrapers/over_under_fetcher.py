#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
改进的大小球赔率爬虫 - 解决并发、重试、反爬虫等问题
核心改进：
1. 线程安全的连接池管理
2. 指数退避的智能重试机制  
3. 反爬虫应对策略（UA池轮换）
4. 完善的错误处理和资源管理
5. 全局速率限制
"""

from __future__ import annotations

import time
import random
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

from core.logger import get_logger
from scrapers.proxy_config import apply_proxy_to_session
from scrapers.scrape_overunder import (
    MarketRecord,
    TITAN007_BROWSER_HEADERS,
    ensure_requests,
    _extract_match_info_from_title,
)

try:
    import requests
except ImportError:
    requests = None


class RateLimiter:
    """线程安全的速率限制器"""
    
    def __init__(self, requests_per_second: float = 2.0):
        self.min_interval = 1.0 / requests_per_second
        self.last_request_time = 0
        self.lock = Lock()
    
    def wait(self):
        """等待直到允许发送下一个请求"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                sleep_time = self.min_interval - elapsed
                time.sleep(sleep_time)
            self.last_request_time = time.time()


class OverUnderOddsFetcher:
    """改进的大小球赔率爬虫"""
    
    # User-Agent池（防止被反爬虫识别）
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    ]

    def __init__(
        self, 
        delay: float = 0.5,  # 保留参数兼容性，但会转换为requests_per_second
        workers: int = 3,     # 降低默认并发数
        max_retries: int = 3,
        timeout: int = 15
    ) -> None:
        self.workers = workers
        self.max_retries = max_retries
        self.timeout = timeout
        self.logger = get_logger(self.__class__.__name__)
        
        # 将delay转换为requests_per_second
        requests_per_second = 1.0 / delay if delay > 0 else 2.0
        self.rate_limiter = RateLimiter(requests_per_second)
        
        ensure_requests()
        
        # 创建线程安全的session池
        self._sessions = self._create_session_pool(workers)
        self._session_lock = Lock()
    
    def _create_robust_session(self) -> requests.Session:
        """创建具有重试机制的健壮session"""
        session = requests.Session()
        
        # 配置重试策略（指数退避）
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            raise_on_status=False
        )
        
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=20
        )
        
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # 设置随机User-Agent
        headers = dict(TITAN007_BROWSER_HEADERS)
        headers['User-Agent'] = random.choice(self.USER_AGENTS)
        session.headers.update(headers)
        
        # Apply tunnel proxy (if configured via env vars)
        apply_proxy_to_session(session)

        # 使用代理时部分站点证书验证可能失败，统一关闭验证
        from scrapers.proxy_config import get_proxy_config
        if get_proxy_config():
            session.verify = False
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        return session
    
    def _create_session_pool(self, size: int) -> List[requests.Session]:
        """创建session池"""
        return [self._create_robust_session() for _ in range(size)]
    
    def _get_session(self) -> requests.Session:
        """线程安全地获取session"""
        with self._session_lock:
            return random.choice(self._sessions)
    
    def _fetch_with_retry(self, match_id: str, url: str) -> Tuple[bool, List[MarketRecord], Optional[str]]:
        """带指数退避的智能重试，返回(成功标志, 记录列表, 错误信息)"""
        session = self._get_session()
        retry_count = 0
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                # 速率限制
                self.rate_limiter.wait()
                
                # 发送请求
                response = session.get(url, timeout=self.timeout, allow_redirects=True)
                
                # 检测反爬虫
                if response.status_code == 403:
                    self.logger.warning(f"Match {match_id}: 403 Forbidden - 可能被反爬虫拦截")
                    session.headers['User-Agent'] = random.choice(self.USER_AGENTS)
                    time.sleep(2 ** attempt)
                    retry_count += 1
                    continue
                
                if response.status_code == 429:
                    self.logger.warning(f"Match {match_id}: 429 Too Many Requests")
                    time.sleep(5 * (2 ** attempt))
                    retry_count += 1
                    continue
                
                if not response.ok:
                    last_error = f"HTTP {response.status_code}"
                    time.sleep(2 ** attempt)
                    retry_count += 1
                    continue
                
                # 解析HTML
                html = self._decode_response(response)
                records = self._parse_html(match_id, html)
                
                if retry_count > 0:
                    self.logger.info(f"Match {match_id}: 成功 (重试{retry_count}次, {len(records)}条记录)")
                
                return True, records, None
                
            except requests.exceptions.Timeout:
                last_error = "Timeout"
                self.logger.warning(f"Match {match_id}: 超时 (attempt {attempt + 1})")
                time.sleep(2 ** attempt)
                retry_count += 1
                
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection Error: {str(e)}"
                self.logger.warning(f"Match {match_id}: 连接错误 (attempt {attempt + 1})")
                time.sleep(2 ** attempt)
                retry_count += 1
                
            except requests.exceptions.RequestException as e:
                last_error = f"Request Exception: {str(e)}"
                self.logger.error(f"Match {match_id}: 请求异常 - {e}")
                time.sleep(2 ** attempt)
                retry_count += 1
                
            except Exception as e:
                last_error = f"Unexpected: {str(e)}"
                self.logger.error(f"Match {match_id}: 未预期错误 - {e}", exc_info=True)
                break
        
        return False, [], last_error
    
    def _decode_response(self, response: requests.Response) -> str:
        """智能解码响应"""
        if response.encoding and response.encoding != 'ISO-8859-1':
            return response.text
        
        raw = response.content
        for enc in ('utf-8', 'gb18030', 'gb2312', 'gbk'):
            try:
                return raw.decode(enc)
            except (UnicodeDecodeError, LookupError):
                continue
        
        return raw.decode('utf-8', errors='ignore')
    
    def _parse_html(self, match_id: str, html: str) -> List[MarketRecord]:
        """解析HTML获取赔率数据"""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("需要 beautifulsoup4")
        
        soup = BeautifulSoup(html, 'html.parser')
        title_el = soup.find('title')
        home, away = (None, None)
        if title_el and title_el.text:
            home, away = _extract_match_info_from_title(title_el.text)
        
        def parse_odds_row(tr_el, bookmaker_name: str, variant_label: str) -> Optional[MarketRecord]:
            tds = tr_el.find_all('td')
            open_cells = []
            for td_el in tds:
                if td_el.has_attr('title') and not td_el.has_attr('oddstype'):
                    style = td_el.get('style', '')
                    if 'display' in style and 'none' in style:
                        continue
                    open_cells.append(td_el)
                if len(open_cells) >= 3:
                    break
            
            line_open = over_open = under_open = time_open = None
            if len(open_cells) >= 3:
                over_open = open_cells[0].get_text(strip=True)
                line_open = open_cells[1].get_text(strip=True)
                under_open = open_cells[2].get_text(strip=True)
                time_open = open_cells[0].get('title')
            
            def pick_close(tr_e):
                last_cells, cur_cells = [], []
                for td_c in tr_e.find_all('td'):
                    ost = td_c.get('oddstype')
                    style = td_c.get('style', '')
                    hidden = ('display' in style and 'none' in style)
                    if ost == 'wholeLastOdds' and not hidden:
                        last_cells.append(td_c)
                    if ost == 'wholeOdds' and not hidden:
                        cur_cells.append(td_c)
                cells = last_cells if len(last_cells) >= 3 else cur_cells
                if len(cells) >= 3:
                    return (cells[1].get_text(strip=True), cells[0].get_text(strip=True), cells[2].get_text(strip=True))
                return (None, None, None)
            
            line_close, over_close, under_close = pick_close(tr_el)
            
            return MarketRecord(
                site='Titan007', league=None, match_id=str(match_id), match_time=None,
                home=home or '', away=away or '', bookmaker=bookmaker_name or None,
                market='O/U', variant=variant_label,
                line_open=line_open, over_odds_open=over_open, under_odds_open=under_open, time_open=time_open,
                line_close=line_close, over_odds_close=over_close, under_odds_close=under_close, time_close=None
            )
        
        records = []
        all_trs = soup.find_all('tr')
        i = 0
        while i < len(all_trs):
            tr = all_trs[i]
            bgc = tr.get('bgcolor')
            cls = tr.get('class') or []
            if not bgc or any('blue_txt' in c for c in cls):
                i += 1
                continue
            tds = tr.find_all('td')
            if len(tds) < 8:
                i += 1
                continue
            bookmaker = tds[1].get_text(strip=True)
            rec = parse_odds_row(tr, bookmaker, 'main')
            if rec:
                records.append(rec)
            j = i + 1
            while j < len(all_trs):
                tr2 = all_trs[j]
                cls2 = tr2.get('class') or []
                bgc2 = tr2.get('bgcolor')
                if bgc2 and not any('blue_txt' in c for c in cls2):
                    break
                if any('blue_txt' in c for c in cls2):
                    tds2 = tr2.find_all('td')
                    variant = tds2[2].get_text(strip=True) if len(tds2) >= 3 else 'sub'
                    rec_sub = parse_odds_row(tr2, bookmaker, variant)
                    if rec_sub:
                        records.append(rec_sub)
                j += 1
            i = j
        
        return records

    def fetch(self, match_ids: List[int]) -> List[MarketRecord]:
        """批量爬取大小球赔率"""
        if not match_ids:
            return []

        ensure_requests()
        
        all_records = []
        failed = []
        base_url = 'https://vip.titan007.com/OverDown_n.aspx?id={}'
        
        if self.workers > 1:
            with ThreadPoolExecutor(max_workers=self.workers) as executor:
                futures = {}
                for mid in match_ids:
                    url = base_url.format(mid)
                    future = executor.submit(self._fetch_with_retry, str(mid), url)
                    futures[future] = mid
                
                for future in as_completed(futures):
                    mid = futures[future]
                    try:
                        success, records, error = future.result()
                        if success:
                            all_records.extend(records)
                        else:
                            failed.append(str(mid))
                            self.logger.error(f"Match {mid}: 失败 - {error}")
                    except Exception as e:
                        failed.append(str(mid))
                        self.logger.error(f"Match {mid}: Future异常 - {e}", exc_info=True)
        else:
            for mid in match_ids:
                url = base_url.format(mid)
                success, records, error = self._fetch_with_retry(str(mid), url)
                if success:
                    all_records.extend(records)
                else:
                    failed.append(str(mid))
        
        total = len(match_ids)
        success_count = total - len(failed)
        self.logger.info(f"爬取完成: 成功 {success_count}/{total}, 失败 {len(failed)}, 获得 {len(all_records)} 条记录")
        
        if failed:
            self.logger.warning(f"失败的比赛: {', '.join(failed[:10])}")
        
        return all_records
    
    def close(self) -> None:
        """关闭所有session"""
        if hasattr(self, '_sessions'):
            for session in self._sessions:
                try:
                    session.close()
                except Exception:
                    pass
            self._sessions.clear()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
