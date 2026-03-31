#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
威廉欧赔历史变化监控服务

定期为当日待监控的比赛爬取威廉希尔的完整赔率变化时间线，
写入 william_odds_history 表，并触发长节点/控赔检测。
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from database.connection import get_connection

logger = get_logger(__name__)

_scrape_lock = threading.Lock()


def scrape_william_history_for_monitored_matches() -> Dict[str, Any]:
    """
    为当前需监控的比赛批量爬取威廉欧赔历史。

    调度器每 30 分钟触发一次即可（历史数据不像实时赔率那样高频变化）。
    """
    if not _scrape_lock.acquire(blocking=False):
        logger.info("威廉历史爬取已在运行，跳过本轮")
        return {'skipped': True}

    try:
        return _do_scrape()
    except Exception as exc:
        logger.error("威廉历史爬取异常: %s", exc, exc_info=True)
        return {'error': str(exc)}
    finally:
        _scrape_lock.release()


def _do_scrape() -> Dict[str, Any]:
    from scrapers.odds_history_scraper import OddsHistoryScraper

    db = get_connection()

    match_rows = db.execute_query(
        """
        SELECT m.match_id, m.match_time
        FROM matches m
        WHERE m.match_time >= NOW() - INTERVAL 2 HOUR
          AND m.match_time < NOW() + INTERVAL 48 HOUR
          AND m.match_status IN ('scheduled', 'live')
        ORDER BY m.match_time
        """,
        fetch='all',
    )

    if not match_rows:
        logger.info("无待爬取威廉历史的比赛")
        return {'matches': 0, 'records': 0}

    # 每次全量重爬：赔率历史会持续新增变化，必须每轮都爬才能保证数据完整
    match_ids = [r['match_id'] for r in match_rows]
    logger.info("开始爬取 %d 场比赛的威廉赔率历史（全量重爬）", len(match_ids))

    with OddsHistoryScraper(delay=0.8, workers=2) as scraper:
        all_records = scraper.scrape_batch(match_ids)
        saved = scraper.save_to_db(all_records, db) if all_records else 0

    logger.info(
        "威廉赔率历史爬取完成: %d 场, %d 条记录, %d 条写入/更新",
        len(match_ids), len(all_records), saved,
    )
    return {
        'matches': len(match_rows),
        'records': len(all_records),
        'saved': saved,
    }


def refresh_william_history_for_match(match_id: int) -> Dict[str, Any]:
    """
    强制刷新单场比赛的威廉赔率历史（用于手动触发或临场更新）。
    """
    from scrapers.odds_history_scraper import OddsHistoryScraper

    db = get_connection()
    with OddsHistoryScraper(delay=0.5) as scraper:
        records = scraper.scrape_match(match_id)
        saved = scraper.save_to_db(records, db) if records else 0

    return {'match_id': match_id, 'records': len(records), 'saved': saved}
