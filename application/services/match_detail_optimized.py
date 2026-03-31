#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化版比赛详情服务
核心优化：
1. 分离静态数据和动态数据
2. 只返回指定数量的公司，不查询全部
3. 使用 Redis 缓存公司优先级映射
4. 预计算统计摘要，避免每次请求都计算
"""

import time
from typing import Any, Dict, List, Optional
from core.logger import get_logger
from utils.cache import cache_get, cache_set, get_cache_key
from .match_detail_optimized_format_ops import (
    build_response_impl,
    format_analysis_impl,
    safe_float_impl,
)
from .match_detail_optimized_query_ops import (
    get_company_count_impl,
    get_match_with_standings_impl,
    get_top_company_analyses_impl,
)

logger = get_logger(__name__)


class OptimizedMatchDetailService:
    """优化版比赛详情服务"""

    def __init__(self):
        from app_helpers import get_team_logo
        from app_constants import PERSONAL_COMPANY_ORDER

        self.get_team_logo = get_team_logo
        self.priority_company_ids = PERSONAL_COMPANY_ORDER
        self._priority_set = set(PERSONAL_COMPANY_ORDER)

    def get_match_detail_fast(self, match_id: str, company_limit: int = 10) -> Dict[str, Any]:
        """快速获取比赛详情 - 核心优化版"""
        start_time = time.time()

        t1 = time.time()
        match_data = self._get_match_with_standings(match_id)
        if not match_data:
            return {"success": False, "error": "Match not found"}
        t2 = time.time()
        logger.debug("[优化] 比赛基本信息+积分榜: %.3fs", t2 - t1)

        t3 = time.time()
        analyses_cache_key = get_cache_key("match_analyses", match_id=match_id, limit=company_limit)
        cached_analyses = cache_get(analyses_cache_key)
        if cached_analyses is not None:
            logger.debug("[优化] 缓存命中: 公司分析 %s (limit=%s)", match_id, company_limit)
            analyses = cached_analyses
        else:
            analyses = self._get_top_company_analyses(match_id, limit=company_limit)
            if analyses:
                cache_set(analyses_cache_key, analyses, expire=60)
        t4 = time.time()
        logger.debug("[优化] 公司分析查询 (limit=%s): %.3fs", company_limit, t4 - t3)

        total_company_count = self._get_company_count(match_id)

        t5 = time.time()
        formatted_analyses = [self._format_analysis(analysis) for analysis in analyses]
        t6 = time.time()
        logger.debug("[优化] 数据格式化: %.3fs", t6 - t5)

        result = self._build_response(match_data, formatted_analyses, total_company_count)

        total_time = time.time() - start_time
        logger.info(
            "[优化] 比赛 %s 详情完成: %.3fs (基本=%.3fs, 分析=%.3fs, 格式化=%.3fs)",
            match_id,
            total_time,
            t2 - t1,
            t4 - t3,
            t6 - t5,
        )

        return {"success": True, "data": result}

    def _get_match_with_standings(self, match_id: str) -> Optional[Dict[str, Any]]:
        """合并查询：比赛基本信息 + 双方积分榜"""
        return get_match_with_standings_impl(self, match_id, logger)

    def _get_top_company_analyses(self, match_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """优化查询：只获取指定数量的公司分析，按优先级排序"""
        return get_top_company_analyses_impl(self, match_id, limit)

    def _get_company_count(self, match_id: str) -> int:
        """获取公司总数（轻量查询）"""
        return get_company_count_impl(match_id)

    @staticmethod
    def _safe_float(value: Any, default: Any = None) -> Any:
        """安全的浮点数转换"""
        return safe_float_impl(value, default)

    def _format_analysis(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        """格式化单个分析数据"""
        return format_analysis_impl(self, analysis)

    def _build_response(
        self,
        match: Dict[str, Any],
        analyses: List[Dict[str, Any]],
        total_company_count: int,
    ) -> Dict[str, Any]:
        """组装响应数据"""
        return build_response_impl(self, match, analyses, total_company_count)


_optimized_service = None


def get_optimized_match_detail_service() -> OptimizedMatchDetailService:
    """获取优化版服务单例"""
    global _optimized_service
    if _optimized_service is None:
        _optimized_service = OptimizedMatchDetailService()
    return _optimized_service


def get_match_detail_fast(match_id: str, company_limit: int = 10) -> Dict[str, Any]:
    """快速获取比赛详情（对外接口）"""
    return get_optimized_match_detail_service().get_match_detail_fast(match_id, company_limit)
