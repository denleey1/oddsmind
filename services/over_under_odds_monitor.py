#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
大小球赔率定时爬取服务

每 30 分钟为当前待监控比赛重爬一次大小球赔率（开盘/即时），
写入 over_under_odds_changes 表，供平系分析使用。
"""

from __future__ import annotations

import threading
from datetime import timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from core.logger import get_logger
from database.connection import get_connection
from utils.timezone_utils import now as get_now

logger = get_logger(__name__)

_scrape_lock = threading.Lock()


# ─────────────────────────────────────────────
#  公司名称解析（复用 monitoring_initialization_service 的逻辑）
# ─────────────────────────────────────────────

def _resolve_company_id(bookmaker: Optional[str]) -> Optional[int]:
    """根据庄家名称字符串映射到内部 company_id。"""
    if not bookmaker:
        return None

    def norm(text: str) -> str:
        return (
            text.lower()
            .replace("*", "")
            .replace("（", "(")
            .replace("）", ")")
            .replace("封", "")
            .replace(" ", "")
        )

    normalized = norm(bookmaker.strip())

    # 常用前缀别名
    alias_prefix = {
        "36": 281,   # Bet365
        "澳":  80,   # 澳门
        "crown": 545,
        "crow":  545,
        "易":   659,
        "18":   976,
    }
    for key, cid in alias_prefix.items():
        if normalized.startswith(key):
            return cid

    return None


# ─────────────────────────────────────────────
#  辅助：MarketRecord → OverUnderOddsChangeModel
# ─────────────────────────────────────────────

def _records_to_models(records) -> list:
    from database.models import OverUnderOddsChangeModel
    from calculation.poisson_live import parse_line_str, to_decimal_odds, parse_timestamp

    def dec(v) -> Optional[Decimal]:
        if v is None:
            return None
        try:
            return Decimal(str(round(float(v), 6)))
        except Exception:
            return None

    now_ts = get_now()
    models = []
    for record in records:
        company_id = _resolve_company_id(getattr(record, "bookmaker", None))
        if not company_id:
            continue

        try:
            match_id = int(str(record.match_id).strip())
        except (ValueError, TypeError):
            continue

        line = parse_line_str(getattr(record, "line_close", None))
        if line is None:
            line = parse_line_str(getattr(record, "line_open", None))
        if line is None:
            continue

        over_c  = to_decimal_odds(getattr(record, "over_odds_close",  None))
        under_c = to_decimal_odds(getattr(record, "under_odds_close", None))
        if over_c is None or under_c is None:
            over_c  = to_decimal_odds(getattr(record, "over_odds_open",  None))
            under_c = to_decimal_odds(getattr(record, "under_odds_open", None))
        if over_c is None or under_c is None:
            continue

        over_o  = to_decimal_odds(getattr(record, "over_odds_open",  None))
        under_o = to_decimal_odds(getattr(record, "under_odds_open", None))

        parsed_ts = (
            parse_timestamp(getattr(record, "time_close", None))
            or parse_timestamp(getattr(record, "time_open", None))
        )
        if parsed_ts:
            # 统一去掉时区信息，避免 offset-naive vs offset-aware 比较错误
            naive_ts = parsed_ts.replace(tzinfo=None) if hasattr(parsed_ts, 'tzinfo') and parsed_ts.tzinfo else parsed_ts
            naive_now = now_ts.replace(tzinfo=None) if hasattr(now_ts, 'tzinfo') and now_ts.tzinfo else now_ts
            last_updated = naive_ts if naive_ts > naive_now - timedelta(hours=48) else naive_now
        else:
            last_updated = now_ts

        models.append(
            OverUnderOddsChangeModel(
                match_id=match_id,
                company_id=int(company_id),
                market_line=line,
                over_open=dec(over_o),
                under_open=dec(under_o),
                over_current=dec(over_c),
                under_current=dec(under_c),
                market="over_under",
                variant=getattr(record, "variant", None) or "main",
                last_updated=last_updated,
            )
        )
    return models


# ─────────────────────────────────────────────
#  对外接口：定时调度调用
# ─────────────────────────────────────────────

def scrape_over_under_for_monitored_matches() -> Dict[str, Any]:
    """
    为当前待监控比赛批量爬取大小球赔率。

    调度器每 30 分钟触发一次。
    """
    if not _scrape_lock.acquire(blocking=False):
        logger.info("大小球爬取已在运行，跳过本轮")
        return {"skipped": True}

    try:
        return _do_scrape()
    except Exception as exc:
        logger.error("大小球爬取异常: %s", exc, exc_info=True)
        return {"error": str(exc)}
    finally:
        _scrape_lock.release()


def _do_scrape() -> Dict[str, Any]:
    from scrapers.over_under_fetcher import OverUnderOddsFetcher
    from database.manager import DatabaseManager

    db = get_connection()

    # 与威廉历史保持同样的时间窗口：开赛前 48 h 到开赛后 2 h
    match_rows = db.execute_query(
        """
        SELECT m.match_id
        FROM matches m
        WHERE m.match_time >= NOW() - INTERVAL 2 HOUR
          AND m.match_time < NOW() + INTERVAL 48 HOUR
          AND m.match_status IN ('scheduled', 'live')
        ORDER BY m.match_time
        """,
        fetch="all",
    )

    if not match_rows:
        logger.info("无待爬取大小球的比赛")
        return {"matches": 0, "records": 0, "saved": 0}

    match_ids = [r["match_id"] for r in match_rows]
    logger.info("开始爬取 %d 场比赛的大小球赔率（全量重爬）", len(match_ids))

    fetcher = OverUnderOddsFetcher(delay=0.8, workers=2)
    raw_records = fetcher.fetch(match_ids)

    if not raw_records:
        logger.info("大小球爬取无数据返回")
        return {"matches": len(match_ids), "records": 0, "saved": 0}

    models = _records_to_models(raw_records)
    if not models:
        logger.warning("大小球数据无法解析为有效模型，跳过写库")
        return {"matches": len(match_ids), "records": len(raw_records), "saved": 0}

    db_manager = DatabaseManager()
    saved = db_manager.bulk_upsert_over_under_odds_changes(models)

    logger.info(
        "大小球爬取完成: %d 场, %d 条原始记录, %d 条写入/更新",
        len(match_ids), len(raw_records), saved,
    )
    return {"matches": len(match_ids), "records": len(raw_records), "saved": saved}
