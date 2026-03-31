#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Monitoring initialization service extracted from legacy app_services module."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from core.logger import get_logger
from utils.timezone_utils import now as get_now
from config.companies_config import COMPANIES_CONFIG
from database.models import AsianHandicapOddsModel, OddsChangeModel, OverUnderOddsChangeModel
from calculation.poisson_live import parse_line_str, to_decimal_odds, parse_timestamp
from scrapers.over_under_fetcher import OverUnderOddsFetcher
from scrapers.asian_handicap_fetcher import AsianHandicapFetcher

logger = get_logger(__name__)


def _build_company_lookup():
    lookup = {}
    for company in COMPANIES_CONFIG.values():
        for name in (company.name_en, company.name_cn):
            if not name:
                continue
            norm = name.strip().lower()
            if norm:
                lookup.setdefault(norm, company.company_id)
                lookup.setdefault(norm.replace(" ", ""), company.company_id)
    return lookup


COMPANY_NAME_LOOKUP = _build_company_lookup()


class MonitoringInitializationService:
    """监控初始化服务"""

    def __init__(self, scraper):
        self.scraper = scraper
        self.over_under_fetcher = OverUnderOddsFetcher()
        self.asian_handicap_fetcher = AsianHandicapFetcher(workers=3, delay=0.5)

    @staticmethod
    def _resolve_company_id(bookmaker: Optional[str]) -> Optional[int]:
        """
        更健壮的公司别名解析：
        - 统一去除空格/星号/括号等符号
        - 支持常见别名与前缀匹配
        - 先精确后模糊
        """
        if not bookmaker:
            return None

        raw = bookmaker.strip().lower()
        if not raw:
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

        normalized = norm(raw)

        direct = COMPANY_NAME_LOOKUP.get(normalized) or COMPANY_NAME_LOOKUP.get(normalized.replace(" ", ""))
        if direct:
            return direct

        alias_exact = {
            "澳": 80,
            "crown": 545,
            "crow": 545,
            "36": 281,
            "易": 659,
            "18": 976,
        }
        for key, company_id in alias_exact.items():
            if normalized.startswith(key):
                return company_id

        if len(normalized) >= 2:
            for known_name, company_id in COMPANY_NAME_LOOKUP.items():
                if not known_name:
                    continue
                known_normalized = norm(known_name)
                if not known_normalized:
                    continue
                if known_normalized.startswith(normalized) or normalized.startswith(known_normalized):
                    return company_id

        return None

    @staticmethod
    def _decimal_or_none(value: Optional[float]) -> Optional[Decimal]:
        if value is None:
            return None
        return Decimal(str(round(value, 6)))

    def _fetch_over_under_records(self, match_ids: List[int]):
        if not match_ids:
            return []
        records = self.over_under_fetcher.fetch(match_ids)
        if not records:
            return []
        allowed = {int(mid) for mid in match_ids}
        filtered = []
        for record in records:
            try:
                match_id = int(str(record.match_id).strip())
            except (ValueError, TypeError):
                continue
            if match_id in allowed:
                filtered.append(record)
        return filtered

    def _build_over_under_models(self, match_ids: List[int], records):
        models: List[OverUnderOddsChangeModel] = []
        if not records:
            return models
        for record in records:
            company_id = self._resolve_company_id(getattr(record, "bookmaker", None))
            if not company_id:
                continue
            try:
                match_id = int(str(record.match_id).strip())
            except (ValueError, TypeError):
                continue

            line_mid = parse_line_str(getattr(record, "line_close", None))
            if line_mid is None:
                line_mid = parse_line_str(getattr(record, "line_open", None))
            if line_mid is None:
                continue

            over_current = to_decimal_odds(getattr(record, "over_odds_close", None))
            under_current = to_decimal_odds(getattr(record, "under_odds_close", None))
            if over_current is None or under_current is None:
                over_current = to_decimal_odds(getattr(record, "over_odds_open", None))
                under_current = to_decimal_odds(getattr(record, "under_odds_open", None))
            if over_current is None or under_current is None:
                continue

            over_open = to_decimal_odds(getattr(record, "over_odds_open", None))
            under_open = to_decimal_odds(getattr(record, "under_odds_open", None))

            now_local = get_now()
            parsed_ts = parse_timestamp(getattr(record, "time_close", None)) or parse_timestamp(
                getattr(record, "time_open", None)
            )
            last_updated = parsed_ts or now_local
            try:
                from datetime import timedelta

                if last_updated < now_local - timedelta(hours=48):
                    last_updated = now_local
            except Exception:
                last_updated = now_local

            variant = getattr(record, "variant", None) or "main"
            models.append(
                OverUnderOddsChangeModel(
                    match_id=match_id,
                    company_id=int(company_id),
                    market_line=line_mid,
                    over_open=self._decimal_or_none(over_open),
                    under_open=self._decimal_or_none(under_open),
                    over_current=self._decimal_or_none(over_current),
                    under_current=self._decimal_or_none(under_current),
                    market="over_under",
                    variant=variant,
                    last_updated=last_updated,
                )
            )
        return models

    def process_scraping_result(
        self,
        match_id: str,
        scraping_result: Any,
        initial_snapshot: Dict,
        odds_changes_to_save: List,
    ) -> None:
        """处理单个比赛的爬取结果"""
        logger.info(
            f"处理比赛 {match_id}: success={getattr(scraping_result, 'success', 'N/A')}, "
            f"data_exists={getattr(scraping_result, 'data', None) is not None}"
        )

        if not (hasattr(scraping_result, "success") and scraping_result.success and scraping_result.data):
            return

        match_data = scraping_result.data
        logger.info(
            f"比赛 {match_id} 数据类型: {type(match_data)}, "
            f"包含odds: {'odds' in match_data if isinstance(match_data, dict) else False}"
        )

        if not (isinstance(match_data, dict) and "odds" in match_data):
            return

        initial_snapshot[match_id] = {}
        now_local = get_now()

        for odds_record in match_data["odds"]:
            company_id = odds_record.get("company_id")
            if not company_id:
                continue

            snapshot_data = {
                "initial_home": odds_record.get("initial_home"),
                "initial_draw": odds_record.get("initial_draw"),
                "initial_away": odds_record.get("initial_away"),
                "initial_return_rate": odds_record.get("initial_return_rate"),
                "current_home": odds_record.get("current_home"),
                "current_draw": odds_record.get("current_draw"),
                "current_away": odds_record.get("current_away"),
                "current_return_rate": odds_record.get("current_return_rate"),
                "_db_written": False,
            }
            initial_snapshot[match_id][company_id] = snapshot_data

            change_model = OddsChangeModel(
                match_id=match_id,
                company_id=company_id,
                initial_home=odds_record.get("initial_home"),
                initial_draw=odds_record.get("initial_draw"),
                initial_away=odds_record.get("initial_away"),
                initial_return_rate=odds_record.get("initial_return_rate"),
                current_home=odds_record.get("current_home"),
                current_draw=odds_record.get("current_draw"),
                current_away=odds_record.get("current_away"),
                current_return_rate=odds_record.get("current_return_rate"),
                last_updated=now_local,
            )
            odds_changes_to_save.append(change_model)

    def scrape_initial_odds(self, match_ids: List[str]) -> Tuple[Dict, List, List]:
        """抓取初始赔率。"""
        logger.info(f"开始抓取 {len(match_ids)} 场比赛的初始赔率...")

        initial_scrape_result = self.scraper.scrape_with_all_companies(match_ids, skip_existing=False)
        initial_snapshot = {}
        odds_changes_to_save: List[OddsChangeModel] = []
        ou_changes_to_save: List[OverUnderOddsChangeModel] = []

        if initial_scrape_result.success and initial_scrape_result.data:
            logger.info(f"成功抓取到 {len(initial_scrape_result.data)} 场比赛的赔率数据")
            for match_id, scraping_result in initial_scrape_result.data.items():
                self.process_scraping_result(match_id, scraping_result, initial_snapshot, odds_changes_to_save)
        else:
            logger.warning("初始赔率抓取失败或无数据")

        numeric_match_ids: List[int] = []
        for match_id in match_ids:
            try:
                numeric_match_ids.append(int(match_id))
            except (ValueError, TypeError):
                logger.warning(f"跳过无法转换为数字的比赛ID: {match_id}")

        if numeric_match_ids:
            numeric_match_ids = sorted(set(numeric_match_ids))
            try:
                ou_records = self._fetch_over_under_records(numeric_match_ids)
                if ou_records:
                    ou_changes_to_save = self._build_over_under_models(numeric_match_ids, ou_records)
                    logger.info("大小球赔率抓取成功: %s 条记录", len(ou_changes_to_save))
            except Exception as exc:
                logger.error("抓取大小球赔率时发生错误: %s", exc, exc_info=True)

        ah_models_to_save: List[AsianHandicapOddsModel] = []
        if numeric_match_ids:
            try:
                ah_records = self.asian_handicap_fetcher.fetch(numeric_match_ids)
                if ah_records:
                    ah_models_to_save = self._build_asian_handicap_models(ah_records)
                    logger.info("亚盘赔率抓取成功: %s 条记录", len(ah_models_to_save))
            except Exception as exc:
                logger.error("抓取亚盘赔率时发生错误: %s", exc, exc_info=True)

        return initial_snapshot, odds_changes_to_save, ou_changes_to_save, ah_models_to_save

    @staticmethod
    def _build_asian_handicap_models(records) -> List[AsianHandicapOddsModel]:
        from datetime import datetime
        now = datetime.now()
        models: List[AsianHandicapOddsModel] = []
        for r in records:
            models.append(AsianHandicapOddsModel(
                match_id=r.match_id,
                company_id=r.company_id,
                initial_home_odds=r.initial_home_odds,
                initial_handicap_line=r.initial_handicap_line,
                initial_away_odds=r.initial_away_odds,
                current_home_odds=r.current_home_odds,
                current_handicap_line=r.current_handicap_line,
                current_away_odds=r.current_away_odds,
                scraped_at=now,
            ))
        return models


__all__ = ["COMPANY_NAME_LOOKUP", "MonitoringInitializationService"]

