import argparse
import csv
import datetime as dt
import json
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

try:
    import requests
except ImportError:  # Fallback if requests isn't available
    requests = None


def ensure_requests():
    global requests
    if requests is None:
        raise RuntimeError(
            "Missing dependency 'requests'. Install with: pip install requests"
        )


@dataclass
class MarketRecord:
    site: str
    league: Optional[str]
    match_id: str
    match_time: Optional[str]
    home: str
    away: str
    bookmaker: Optional[str]
    market: str  # e.g., 'O/U'
    variant: Optional[str]  # 'main' or e.g. '盘2'
    line_open: Optional[str]
    over_odds_open: Optional[str]
    under_odds_open: Optional[str]
    time_open: Optional[str]
    line_close: Optional[str]
    over_odds_close: Optional[str]
    under_odds_close: Optional[str]
    time_close: Optional[str]
    detail_url: Optional[str] = None
    current_is_prematch: bool = True
    current_source: Optional[str] = None

TITAN007_BROWSER_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Accept-Language": "zh-CN,zh;q=0.9",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-CH-UA": "\"Chromium\";v=\"140\", \"Not=A?Brand\";v=\"24\", \"Google Chrome\";v=\"140\"",
    "Sec-CH-UA-Mobile": "?0",
    "Sec-CH-UA-Platform": "\"Windows\"",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
}

def _dot_get(d: Any, path: Optional[str], default=None):
    if path is None or path == "":
        return d
    cur = d
    for part in path.split('.'):
        if cur is None:
            return default
        if isinstance(cur, list):
            try:
                idx = int(part)
                cur = cur[idx]
            except Exception:
                return default
        elif isinstance(cur, dict):
            cur = cur.get(part, default)
        else:
            return default
    return cur


def _to_date(s: str) -> str:
    # Accept YYYY-MM-DD, YYYY/MM/DD, or epoch seconds
    s = str(s).strip()
    try:
        if s.isdigit():
            return dt.datetime.utcfromtimestamp(int(s)).strftime('%Y-%m-%d')
        for fmt in ('%Y-%m-%d', '%Y/%m/%d'):
            return dt.datetime.strptime(s, fmt).strftime('%Y-%m-%d')
    except Exception:
        pass
    # fallback to today
    return dt.date.today().strftime('%Y-%m-%d')


def _substitute(template: str, **kwargs) -> str:
    out = template
    for k, v in kwargs.items():
        out = out.replace('{' + k + '}', str(v))
    return out


def _parse_header_items(items: List[str]) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    for raw in items:
        if ':' not in raw:
            raise ValueError(f"Invalid header format: {raw!r}. Use 'Name: Value'.")
        name, value = raw.split(':', 1)
        name = name.strip()
        value = value.strip()
        if not name:
            raise ValueError(f"Header name missing in {raw!r}.")
        parsed[name] = value
    return parsed



def _session(headers: Dict[str, str], cookies: Dict[str, str], proxies: Dict[str, str]):
    ensure_requests()
    s = requests.Session()
    if headers:
        s.headers.update(headers)
    if cookies:
        s.cookies.update(cookies)
    if proxies:
        s.proxies.update(proxies)
    # Also apply env-var proxy (tunnel proxy) if no explicit proxies given
    if not proxies:
        try:
            from scrapers.proxy_config import apply_proxy_to_session
            apply_proxy_to_session(s)
        except ImportError:
            pass
    s.headers.setdefault('User-Agent', 'Mozilla/5.0 (compatible; overunder-scraper/1.0)')
    return s


def _get_json(s, url: str, params: Optional[Dict[str, Any]] = None, retry=2, sleep=0.5):
    for i in range(retry + 1):
        r = s.get(url, params=params, timeout=20)
        if r.ok:
            try:
                return r.json()
            except Exception:
                pass
        if i < retry:
            time.sleep(sleep)
    raise RuntimeError(f"Failed to fetch JSON from {url}")


def _get_text(s, url: str, params: Optional[Dict[str, Any]] = None, retry=2, sleep=0.5) -> str:
    for i in range(retry + 1):
        r = s.get(url, params=params, timeout=20)
        if r.ok:
            # Use raw bytes with auto-decoding to handle gb2312/gb18030 pages
            try:
                return _decode_bytes_auto(r.content)
            except Exception:
                return r.text
        if i < retry:
            time.sleep(sleep)
    raise RuntimeError(f"Failed to fetch HTML from {url}")


def parse_json_site(site_cfg: Dict[str, Any], date_str: str, s) -> List[MarketRecord]:
    out: List[MarketRecord] = []
    list_url = _substitute(site_cfg['matches_url'], date=date_str)
    matches_json = _get_json(s, list_url)
    matches = _dot_get(matches_json, site_cfg.get('matches_json_path'))
    if not isinstance(matches, list):
        raise RuntimeError(f"Expected list at matches_json_path for site {site_cfg['name']}")

    status_field = site_cfg.get('status_field')
    exclude_status = set(site_cfg.get('exclude_status', ['live', 'inplay']))
    league_field = site_cfg.get('league_field')

    for m in matches:
        status_val = _dot_get(m, status_field) if status_field else None
        if status_val and str(status_val).lower() in exclude_status:
            continue  # skip in-play

        match_id = str(_dot_get(m, site_cfg['match_id_field']))
        home = str(_dot_get(m, site_cfg['home_field']))
        away = str(_dot_get(m, site_cfg['away_field']))
        match_time = _dot_get(m, site_cfg.get('kickoff_field'))
        league = _dot_get(m, league_field) if league_field else None

        odds_url = _substitute(site_cfg['odds_url'], match_id=match_id)
        odds_json = _get_json(s, odds_url)

        open_path = _dot_get(odds_json, site_cfg['odds_json_paths'].get('open'))
        close_path = _dot_get(odds_json, site_cfg['odds_json_paths'].get('close'))

        # Some endpoints return per-bookmaker arrays; support either object or list
        open_items = open_path if isinstance(open_path, list) else [open_path]
        close_items = close_path if isinstance(close_path, list) else [close_path]

        # Build indexing by bookmaker if possible
        key_field = site_cfg.get('bookmaker_field', 'bookmaker')

        open_index: Dict[str, Any] = {}
        for item in filter(None, open_items):
            bk = str(_dot_get(item, site_cfg.get('open_fields', {}).get('bookmaker', key_field)) or '')
            open_index[bk] = item

        close_index: Dict[str, Any] = {}
        for item in filter(None, close_items):
            bk = str(_dot_get(item, site_cfg.get('close_fields', {}).get('bookmaker', key_field)) or '')
            close_index[bk] = item

        # Union of bookmakers present in either
        bookmakers = set(open_index.keys()) | set(close_index.keys())

        for bk in sorted(bookmakers):
            o = open_index.get(bk)
            c = close_index.get(bk)

            def pick(item, fields_map: Dict[str, str], key: str):
                return _dot_get(item, fields_map.get(key)) if item else None

            open_fields = site_cfg.get('open_fields', {})
            close_fields = site_cfg.get('close_fields', {})

            rec = MarketRecord(
                site=site_cfg['name'],
                league=str(league) if league is not None else None,
                match_id=match_id,
                match_time=str(match_time) if match_time is not None else None,
                home=home,
                away=away,
                bookmaker=bk or None,
                market='O/U',
                variant=None,
                line_open=str(pick(o, open_fields, 'line') or '' ) or None,
                over_odds_open=str(pick(o, open_fields, 'over') or '' ) or None,
                under_odds_open=str(pick(o, open_fields, 'under') or '' ) or None,
                time_open=str(pick(o, open_fields, 'time') or '' ) or None,
                line_close=str(pick(c, close_fields, 'line') or '' ) or None,
                over_odds_close=str(pick(c, close_fields, 'over') or '' ) or None,
                under_odds_close=str(pick(c, close_fields, 'under') or '' ) or None,
                time_close=str(pick(c, close_fields, 'time') or '' ) or None,
            )
            out.append(rec)
    return out


def parse_html_site(site_cfg: Dict[str, Any], date_str: str, s) -> List[MarketRecord]:
    # Lightweight HTML parser using built-in HTMLParser via bs4 if installed
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        raise RuntimeError("HTML parsing requires beautifulsoup4. Install with: pip install beautifulsoup4")

    out: List[MarketRecord] = []
    list_url = _substitute(site_cfg['matches_url'], date=date_str)
    html = _get_text(s, list_url)
    soup = BeautifulSoup(html, 'html.parser')

    row_sel = site_cfg['matches_selector']
    rows = soup.select(row_sel)
    status_sel = site_cfg.get('status_selector')
    exclude_status = set(map(str.lower, site_cfg.get('exclude_status', ['live', 'inplay'])))

    for r in rows:
        status_text = None
        if status_sel:
            el = r.select_one(status_sel)
            status_text = el.get_text(strip=True).lower() if el else None
        if status_text and status_text in exclude_status:
            continue

        match_id_attr = site_cfg.get('match_id_attr')  # e.g., data-id
        match_id_sel = site_cfg.get('match_id_selector')
        if match_id_attr and r.has_attr(match_id_attr):
            match_id = r[match_id_attr]
        elif match_id_sel:
            me = r.select_one(match_id_sel)
            match_id = me.get_text(strip=True) if me else ''
        else:
            match_id = ''

        def text(sel: Optional[str]) -> Optional[str]:
            if not sel:
                return None
            el = r.select_one(sel)
            return el.get_text(strip=True) if el else None

        home = text(site_cfg.get('home_selector')) or ''
        away = text(site_cfg.get('away_selector')) or ''
        kickoff = text(site_cfg.get('kickoff_selector'))
        league = text(site_cfg.get('league_selector'))

        odds_page_url = _substitute(site_cfg['odds_page_url'], match_id=match_id)
        odds_html = _get_text(s, odds_page_url)
        odds = BeautifulSoup(odds_html, 'html.parser')

        # Expect a bookmaker table: one row per bookmaker with open/close columns
        book_rows = odds.select(site_cfg['bookmaker_rows_selector'])
        for br in book_rows:
            bk_name_el = br.select_one(site_cfg['bookmaker_name_selector'])
            bookmaker = bk_name_el.get_text(strip=True) if bk_name_el else None

            def otext(sel: Optional[str]) -> Optional[str]:
                if not sel:
                    return None
                el = br.select_one(sel)
                return el.get_text(strip=True) if el else None

            rec = MarketRecord(
                site=site_cfg['name'],
                league=league,
                match_id=str(match_id),
                match_time=kickoff,
                home=home,
                away=away,
                bookmaker=bookmaker,
                market='O/U',
                variant=None,
                line_open=otext(site_cfg.get('open_line_selector')),
                over_odds_open=otext(site_cfg.get('open_over_selector')),
                under_odds_open=otext(site_cfg.get('open_under_selector')),
                time_open=otext(site_cfg.get('open_time_selector')),
                line_close=otext(site_cfg.get('close_line_selector')),
                over_odds_close=otext(site_cfg.get('close_over_selector')),
                under_odds_close=otext(site_cfg.get('close_under_selector')),
                time_close=otext(site_cfg.get('close_time_selector')),
            )
            out.append(rec)

    return out


def _decode_bytes_auto(data: bytes) -> str:
    # Prefer gb18030 for Chinese pages; fallback to utf-8
    for enc in ('gb18030', 'utf-8', 'latin-1'):
        try:
            return data.decode(enc)
        except Exception:
            continue
    return data.decode('utf-8', errors='ignore')


def _extract_match_info_from_title(title: str) -> Tuple[Optional[str], Optional[str]]:
    # Try to split 'TeamA VS TeamB'
    m = re.search(r"\s*([^\(\)\-\|]+?)\s*VS\s*([^\(\)\-\|]+?)\s*", title, re.IGNORECASE)
    if m:
        home = m.group(1).strip()
        away = m.group(2).strip()
        return home, away
    return None, None


def parse_titan007_overdown_local(file_paths: List[str]) -> List[MarketRecord]:
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except Exception:
        raise RuntimeError("HTML parsing requires beautifulsoup4. Install with: pip install beautifulsoup4")

    records: List[MarketRecord] = []

    for fp in file_paths:
        if not os.path.isfile(fp):
            continue
        with open(fp, 'rb') as f:
            raw = f.read()
        text = _decode_bytes_auto(raw)

        # Try to extract a captured URL line like 'https://...OverDown_n.aspx?id=2789129'
        first_line = text.splitlines()[0].strip() if text else ''
        match_id = None
        m = re.search(r"id=(\d+)", first_line)
        if m:
            match_id = m.group(1)

        soup = BeautifulSoup(text, 'html.parser')

        # If match_id not found, search any href containing id=...
        if not match_id:
            a = soup.find('a', href=re.compile(r'id=\d+'))
            if a and a.has_attr('href'):
                m2 = re.search(r"id=(\d+)", a['href'])
                if m2:
                    match_id = m2.group(1)
        match_id = match_id or ''

        # Extract teams from <title>
        title_el = soup.find('title')
        home, away = (None, None)
        if title_el and title_el.text:
            home, away = _extract_match_info_from_title(title_el.text)

        # Locate bookmaker rows: main rows have bgcolor attribute, and are not detail/history rows (no class 'blue_txt')
        # Helper to parse a single odds row (main or sub)
        def parse_odds_row(tr_el, bookmaker_name: str, variant_label: str) -> Optional[MarketRecord]:
            tds = tr_el.find_all('td')
            # Opening trio
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

            # Closing trio (prefer wholeLastOdds)
            def pick_close(tr_e) -> Tuple[Optional[str], Optional[str], Optional[str]]:
                last_cells = []
                cur_cells = []
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
                    return (
                        cells[1].get_text(strip=True),
                        cells[0].get_text(strip=True),
                        cells[2].get_text(strip=True),
                    )
                return (None, None, None)
            line_close, over_close, under_close = pick_close(tr_el)

            return MarketRecord(
                site='Titan007',
                league=None,
                match_id=str(match_id),
                match_time=None,
                home=home or '',
                away=away or '',
                bookmaker=bookmaker_name or None,
                market='O/U',
                variant=variant_label,
                line_open=line_open,
                over_odds_open=over_open,
                under_odds_open=under_open,
                time_open=time_open,
                line_close=line_close,
                over_odds_close=over_close,
                under_odds_close=under_close,
                time_close=None,
            )

        # Iterate main rows and attach subsequent blue_txt rows as sub-handicaps
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
            rec_main = parse_odds_row(tr, bookmaker, 'main')
            if rec_main:
                records.append(rec_main)

            # Walk following blue_txt rows
            j = i + 1
            while j < len(all_trs):
                tr2 = all_trs[j]
                cls2 = tr2.get('class') or []
                bgc2 = tr2.get('bgcolor')
                if bgc2 and not any('blue_txt' in c for c in cls2):
                    break  # next company block
                if any('blue_txt' in c for c in cls2):
                    tds2 = tr2.find_all('td')
                    variant_label = tds2[2].get_text(strip=True) if len(tds2) >= 3 else 'sub'
                    rec_sub = parse_odds_row(tr2, bookmaker, variant_label)
                    if rec_sub:
                        records.append(rec_sub)
                j += 1
            i = j

    return records


def parse_titan007_overdown_network(ids: Optional[List[str]] = None,
                                    urls: Optional[List[str]] = None,
                                    headers: Optional[Dict[str, str]] = None,
                                    cookies: Optional[Dict[str, str]] = None,
                                    proxies: Optional[Dict[str, str]] = None,
                                    delay: float = 0.5,
                                    workers: int = 1,
                                    session: Optional[Any] = None) -> List[MarketRecord]:
    """Fetch Over/Under page(s) online and parse initial/closing odds per bookmaker.

    - ids: list of match IDs (OverDown_n.aspx?id=ID)
    - urls: list of full OverDown page URLs (used to extract ids)
    """
    ensure_requests()
    s = _session(headers or {}, cookies or {}, proxies or {})

    targets: List[Tuple[str, str]] = []  # list of (id, url)
    base = 'https://vip.titan007.com/OverDown_n.aspx?id={id}'

    if urls:
        for u in urls:
            m = re.search(r"id=(\d+)", u)
            if m:
                mid = m.group(1)
                targets.append((mid, _substitute(base, id=mid)))
    if ids:
        for mid in ids:
            targets.append((str(mid), _substitute(base, id=str(mid))))

    # De-duplicate by id
    seen = set()
    uniq_targets = []
    for mid, url in targets:
        if mid in seen:
            continue
        seen.add(mid)
        uniq_targets.append((mid, url))

    all_records: List[MarketRecord] = []
    def _parse_one(mid: str, html: str) -> List[MarketRecord]:
        try:
            from bs4 import BeautifulSoup  # type: ignore
        except Exception:
            raise RuntimeError("HTML parsing requires beautifulsoup4. Install with: pip install beautifulsoup4")
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
            def pick_close(tr_e) -> Tuple[Optional[str], Optional[str], Optional[str]]:
                last_cells = []
                cur_cells = []
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
                    return (
                        cells[1].get_text(strip=True),
                        cells[0].get_text(strip=True),
                        cells[2].get_text(strip=True),
                    )
                return (None, None, None)
            line_close, over_close, under_close = pick_close(tr_el)
            return MarketRecord(
                site='Titan007',
                league=None,
                match_id=str(mid),
                match_time=None,
                home=home or '',
                away=away or '',
                bookmaker=bookmaker_name or None,
                market='O/U',
                variant=variant_label,
                line_open=line_open,
                over_odds_open=over_open,
                under_odds_open=under_open,
                time_open=time_open,
                line_close=line_close,
                over_odds_close=over_close,
                under_odds_close=under_close,
                time_close=None,
            )

        page_records: List[MarketRecord] = []
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
            rec_main = parse_odds_row(tr, bookmaker, 'main')
            if rec_main:
                page_records.append(rec_main)
            j = i + 1
            while j < len(all_trs):
                tr2 = all_trs[j]
                cls2 = tr2.get('class') or []
                bgc2 = tr2.get('bgcolor')
                if bgc2 and not any('blue_txt' in c for c in cls2):
                    break
                if any('blue_txt' in c for c in cls2):
                    tds2 = tr2.find_all('td')
                    variant_label = tds2[2].get_text(strip=True) if len(tds2) >= 3 else 'sub'
                    rec_sub = parse_odds_row(tr2, bookmaker, variant_label)
                    if rec_sub:
                        page_records.append(rec_sub)
                j += 1
            i = j
        return page_records

    all_records: List[MarketRecord] = []

    if workers and workers > 1:
        def fetch(mid: str, url: str) -> Tuple[str, Optional[str]]:
            # per-thread session
            ss = _session(headers or {}, cookies or {}, proxies or {})
            try:
                html = _get_text(ss, url)
                return mid, html
            except Exception as e:
                print(f"Warn: fetch failed for {mid}: {e}", file=sys.stderr)
                return mid, None

        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(fetch, mid, url): (mid, url) for mid, url in uniq_targets}
            for fut in as_completed(futs):
                mid, html = fut.result()
                if not html:
                    continue
                all_records.extend(_parse_one(mid, html))
    else:
        for mid, url in uniq_targets:
            try:
                html = _get_text(s, url)
                all_records.extend(_parse_one(mid, html))
            except Exception as e:
                print(f"Warn: fetch failed for {mid}: {e}", file=sys.stderr)
            if delay:
                time.sleep(delay)

    return all_records


def run_from_config(cfg: Dict[str, Any], date_str: str) -> List[MarketRecord]:
    headers = cfg.get('headers', {})
    cookies = cfg.get('cookies', {})
    proxies = cfg.get('proxies', {})
    s = _session(headers, cookies, proxies)

    all_records: List[MarketRecord] = []
    for site in cfg.get('sites', []):
        site_type = site.get('type', 'json').lower()
        if site_type == 'json':
            records = parse_json_site(site, date_str, s)
        elif site_type == 'html':
            records = parse_html_site(site, date_str, s)
        else:
            raise ValueError(f"Unknown site type: {site_type}")
        all_records.extend(records)
    return all_records


def read_ids_from_sqlite(db_path: str, table: str = 'matches', id_column: str = 'match_id', where: Optional[str] = None, sql: Optional[str] = None) -> List[str]:
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        if sql:
            cur.execute(sql)
        else:
            q = f"SELECT {id_column} FROM {table}"
            if where:
                q += f" WHERE {where}"
            cur.execute(q)
        ids = [str(row[0]) for row in cur.fetchall()]
        return ids
    finally:
        con.close()


def write_to_sqlite(db_path: str, table: str, records: List[MarketRecord]):
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table} (
                site TEXT,
                league TEXT,
                match_id TEXT,
                match_time TEXT,
                home TEXT,
                away TEXT,
                bookmaker TEXT,
                market TEXT,
                variant TEXT,
                line_open TEXT,
                over_odds_open TEXT,
                under_odds_open TEXT,
                time_open TEXT,
                line_close TEXT,
                over_odds_close TEXT,
                under_odds_close TEXT,
                time_close TEXT,
                UNIQUE(site, match_id, bookmaker, market, variant)
            )
            """
        )
        con.commit()

        rows = []
        for r in records:
            d = asdict(r)
            # Normalize variant to empty string for uniqueness stability
            variant = d.get('variant') or ''
            rows.append((
                d.get('site'), d.get('league'), d.get('match_id'), d.get('match_time'),
                d.get('home'), d.get('away'), d.get('bookmaker'), d.get('market'), variant,
                d.get('line_open'), d.get('over_odds_open'), d.get('under_odds_open'), d.get('time_open'),
                d.get('line_close'), d.get('over_odds_close'), d.get('under_odds_close'), d.get('time_close'),
            ))

        cur.executemany(
            f"""
            INSERT OR REPLACE INTO {table} (
                site, league, match_id, match_time, home, away, bookmaker, market, variant,
                line_open, over_odds_open, under_odds_open, time_open,
                line_close, over_odds_close, under_odds_close, time_close
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            rows,
        )
        con.commit()
    finally:
        con.close()


def write_output(records: List[MarketRecord], out_path: str, fmt: str):
    if fmt == 'csv':
        if not records:
            # Still write header
            fields = [f.name for f in MarketRecord.__dataclass_fields__.values()]
        else:
            fields = list(asdict(records[0]).keys())
        with open(out_path, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in records:
                w.writerow(asdict(r))
    elif fmt == 'json':
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)
    else:
        raise ValueError('Unsupported output format, use csv or json')


def main(argv=None):
    p = argparse.ArgumentParser(description='Over/Under scraper (opening & closing odds only, no in-play).')
    p.add_argument('--config', help='Path to config JSON defining sites and selectors')
    p.add_argument('--local-titan007', nargs='+', help='Parse local Titan007 Over/Under HTML files (e.g., saved pages)')
    p.add_argument('--titan007-ids', nargs='+', help='Online: Titan007 match IDs for Over/Under page')
    p.add_argument('--titan007-urls', nargs='+', help='Online: Titan007 Over/Under page URLs')
    p.add_argument('--cookie', default=None, help='Optional Cookie header for online requests')
    p.add_argument('--ua', default=None, help='Optional User-Agent header for online requests')
    p.add_argument('--header', action='append', default=[], help="Additional HTTP header in 'Name: Value' format. Repeatable.")
    p.add_argument('--headers-json', help='Path to JSON file providing extra headers as a mapping.')
    p.add_argument('--no-titan007-browser-headers', action='store_true', help='Disable built-in Titan007 browser-style headers.')
    p.add_argument('--delay', type=float, default=0.5, help='Delay between online requests (seconds)')
    p.add_argument('--workers', type=int, default=6, help='Concurrent workers for online fetching')
    # SQLite input for match IDs
    p.add_argument('--sqlite-in', help='Path to SQLite DB to read match IDs')
    p.add_argument('--in-table', default='matches', help='Table name that contains match IDs')
    p.add_argument('--in-id-column', default='match_id', help='Column name for match IDs')
    p.add_argument('--in-where', default=None, help='Optional WHERE clause for selecting match IDs')
    p.add_argument('--in-sql', default=None, help='Custom SQL to select match IDs (first column used)')
    # SQLite output for odds
    p.add_argument('--sqlite-out', help='Path to SQLite DB to write odds')
    p.add_argument('--out-table', default='ou_odds', help='Table name to store odds')
    p.add_argument('--date', default=dt.date.today().strftime('%Y-%m-%d'), help='Date (YYYY-MM-DD)')
    p.add_argument('--out', default='overunder.csv', help='Output file path')
    p.add_argument('--format', default='csv', choices=['csv', 'json'], help='Output format')
    args = p.parse_args(argv)

    # Local Titan007 mode (no network)
    if args.local_titan007:
        records = parse_titan007_overdown_local(args.local_titan007)
    elif args.titan007_ids or args.titan007_urls or args.sqlite_in:
        # Gather IDs from CLI and/or SQLite
        ids: List[str] = []
        if args.titan007_ids:
            ids.extend([str(x) for x in args.titan007_ids])
        if args.sqlite_in:
            ids_from_db = read_ids_from_sqlite(
                args.sqlite_in,
                table=args.in_table,
                id_column=args.in_id_column,
                where=args.in_where,
                sql=args.in_sql,
            )
            ids.extend(ids_from_db)
        # De-duplicate while preserving order
        seen_ids = set()
        ids = [x for x in ids if not (x in seen_ids or seen_ids.add(x))]
        headers: Dict[str, str] = {}
        if not args.no_titan007_browser_headers:
            headers.update(TITAN007_BROWSER_HEADERS)
        if args.headers_json:
            try:
                with open(args.headers_json, 'r', encoding='utf-8') as fh:
                    file_headers = json.load(fh)
            except FileNotFoundError as exc:
                raise SystemExit(f'Headers JSON not found: {args.headers_json}') from exc
            except json.JSONDecodeError as exc:
                raise SystemExit(f'Failed to parse headers JSON: {exc}') from exc
            if not isinstance(file_headers, dict):
                raise SystemExit('Headers JSON must be an object of name: value pairs.')
            headers.update({str(k): str(v) for k, v in file_headers.items()})
        if args.header:
            try:
                headers.update(_parse_header_items(args.header))
            except ValueError as exc:
                raise SystemExit(str(exc)) from exc
        if args.ua:
            headers['User-Agent'] = args.ua
        if args.cookie:
            headers['Cookie'] = args.cookie
        records = parse_titan007_overdown_network(
            ids=ids,
            urls=args.titan007_urls,
            headers=headers,
            cookies={},
            proxies={},
            delay=args.delay,
            workers=args.workers,
        )
    else:
        if not args.config:
            raise SystemExit('Either --local-titan007 or --config must be provided')
        date_str = _to_date(args.date)
        with open(args.config, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        records = run_from_config(cfg, date_str)
    # Write outputs
    if args.sqlite_out:
        write_to_sqlite(args.sqlite_out, args.out_table, records)
        print(f"Stored {len(records)} records to SQLite: {args.sqlite_out} table {args.out_table}")
    if args.out:
        write_output(records, args.out, args.format)
        print(f"Wrote {len(records)} records to {args.out}")


if __name__ == '__main__':
    sys.exit(main())
