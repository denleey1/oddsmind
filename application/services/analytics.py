#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Analytics related helpers reused across views and schedulers."""

from __future__ import annotations

from typing import Any, Dict, List

from application.context import get_logger_for
from application.services.fundamental_analysis_service import FundamentalAnalysisService
from application.services.odds_analysis_service import OddsAnalysisService
from application.services.match_detail_service_provider import get_match_detail_service

_logger = get_logger_for(__name__)
_fundamental_service = FundamentalAnalysisService()
_odds_analysis_service = OddsAnalysisService()


def batch_analyze_fundamental(match_ids: List[str]) -> Any:
    """Run fundamental analysis for the provided matches."""
    return _fundamental_service.batch_analyze_fundamental(match_ids)


def recalculate_all_fundamental() -> Dict[str, Any]:
    """重新计算基本面分析表中所有match_id的基本面分析（覆盖现有结果）"""
    try:
        success_count, failed_count = _fundamental_service.recalculate_all_fundamental()
        return {
            'success': True,
            'success_count': success_count,
            'failed_count': failed_count,
            'total_count': success_count + failed_count
        }
    except Exception as e:
        _logger.error(f"重新计算基本面分析时出错: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


def analyze_existing_odds_changes() -> None:
    """Ensure historical odds changes have been analysed."""
    _odds_analysis_service.analyze_existing_odds_changes()


def get_poisson_prediction(match_id: str) -> Dict[str, Any]:
    """获取比赛的泊松分布预测（延迟加载接口）"""
    from calculation.poisson_calculator import get_poisson_prediction as calc_poisson
    
    try:
        _logger.info(f"开始为比赛 {match_id} 计算泊松分布预测...")
        result = calc_poisson(
            int(match_id), 
            use_dc=True,           # Dixon-Coles修正
            time_decay=True,       # 时间衰减
            half_life_days=150,    # 半衰期150天
            use_bivariate=True     # 双变量泊松(处理相关性)
        )
        _logger.info(f"比赛 {match_id} 的泊松预测计算完成")
        return {'success': True, 'data': result}
    except Exception as e:
        _logger.error(f"为比赛 {match_id} 计算泊松分布时发生错误: {e}", exc_info=True)
        return {'success': False, 'error': f'泊松预测计算失败: {str(e)}'}


def get_match_detail(match_id: str) -> Dict[str, Any]:
    """
    [已恢复] 获取完整比赛详情，包含:
    - 全部公司数据
    - 泊松预测
    - 态度总结
    """
    return get_match_detail_service().get_complete_match_detail(match_id, include_poisson=True)
