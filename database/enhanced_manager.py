#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Database Manager - 数据库专家级优化版本
集成优化的仓库和高级数据库管理功能
"""

from datetime import datetime
import threading
from typing import Any, Dict, Optional

from .optimized_repository import OptimizedCompanyRepository, OptimizedOddsRepository
from .repository import (
    LeagueRepository,
    MatchRepository,
    ScrapingLogRepository,
    StandingRepository,
    TeamRepository,
)
from core.logger import get_logger
from .enhanced_manager_diagnostics_ops import (
    diagnose_database_issues_impl,
    get_enhanced_database_stats_impl,
)
from .enhanced_manager_league_ops import normalize_match_data_impl, store_league_data_impl
from .enhanced_manager_odds_ops import (
    ensure_company_exists_enhanced_impl,
    get_company_from_config_impl,
    normalize_odds_data_enhanced_impl,
    store_multiple_odds_data_enhanced_impl,
    store_odds_data_enhanced_impl,
    update_avg_batch_time_impl,
)


class EnhancedDatabaseManager:
    """
    增强的数据库管理器 - 集成优化仓库和高级功能
    专门解决你遇到的外键约束和并发问题
    """

    def __init__(self):
        self.logger = get_logger(self.__class__.__name__)

        self.odds = OptimizedOddsRepository()
        self.companies = OptimizedCompanyRepository()

        self.leagues = LeagueRepository()
        self.teams = TeamRepository()
        self.matches = MatchRepository()
        self.standings = StandingRepository()
        self.logs = ScrapingLogRepository()

        self._operation_stats = {
            "odds_operations": 0,
            "company_operations": 0,
            "total_records_processed": 0,
            "failed_operations": 0,
            "avg_batch_time": 0.0,
            "last_reset": datetime.utcnow(),
        }

        self._stats_lock = threading.Lock()

        self.logger.info("Enhanced database manager initialized with optimized repositories")

    def store_odds_data_enhanced(self, match_id: int, odds_data: Dict[str, Any]) -> int:
        """增强的赔率数据存储 - 解决外键约束问题"""
        return store_odds_data_enhanced_impl(self, match_id, odds_data)

    def store_multiple_odds_data_enhanced(
        self,
        odds_batch: Dict[int, Dict[str, Any]],
        max_batch_size: int = 500,
    ) -> Dict[int, int]:
        """增强的批量赔率数据存储 - 高性能版本"""
        return store_multiple_odds_data_enhanced_impl(self, odds_batch, max_batch_size=max_batch_size)

    def ensure_company_exists_enhanced(self, company_id: int, company_data: Dict[str, Any]) -> bool:
        """增强的公司存在性检查和创建"""
        return ensure_company_exists_enhanced_impl(self, company_id, company_data)

    def get_enhanced_database_stats(self) -> Dict[str, Any]:
        """获取增强的数据库统计信息"""
        return get_enhanced_database_stats_impl(self)

    def diagnose_database_issues(self) -> Dict[str, Any]:
        """诊断数据库问题 - 专门检查外键约束和数据一致性"""
        return diagnose_database_issues_impl(self)

    def _normalize_odds_data_enhanced(self, odds_data: Dict[str, Any]) -> Dict[str, Any]:
        """增强的赔率数据标准化"""
        return normalize_odds_data_enhanced_impl(self, odds_data)

    def _get_company_from_config(self, company_id: int) -> Optional[Dict[str, Any]]:
        """从配置获取公司信息"""
        return get_company_from_config_impl(self, company_id)

    def _update_avg_batch_time(self, execution_time: float):
        """更新平均批处理时间"""
        update_avg_batch_time_impl(self, execution_time)

    def store_league_data(self, league_data: Dict[str, Any]) -> Dict[str, int]:
        """保持与原DatabaseManager的兼容性"""
        return store_league_data_impl(self, league_data)

    def _normalize_match_data(self, match_data: Dict[str, Any]) -> Dict[str, Any]:
        """标准化比赛数据"""
        return normalize_match_data_impl(match_data)
