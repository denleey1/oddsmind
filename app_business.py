#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
应用业务逻辑模块
从app.py中提取的业务逻辑类和函数，提高代码组织性和可维护性
"""
import os
import json
from typing import Dict, List, Any, Optional
from pathlib import Path
from core.logger import get_logger
from app_helpers import get_company_name_cn

logger = get_logger(__name__)


class CompanySummaryCalculator:
    """公司推荐汇总计算器"""
    
    def __init__(self, project_root: Path):
        """
        初始化计算器并加载推荐映射规则
        
        Args:
            project_root: 项目根目录路径
        """
        self.project_root = project_root
        self.recommendation_mapping: Dict[str, Any] = {}
        self._load_recommendation_mapping()
    
    def _load_recommendation_mapping(self) -> None:
        """加载推荐映射规则"""
        try:
            mapping_file = os.path.join(self.project_root, 'validation_test', 'recommendation_mapping.json')
            with open(mapping_file, 'r', encoding='utf-8') as f:
                mapping_data = json.load(f)
                self.recommendation_mapping = mapping_data.get('recommendations', {})
            logger.info("成功预加载推荐映射规则。")
        except Exception as e:
            logger.error(f"预加载推荐映射规则失败: {e}")
    
    def map_recommendation(self, recommendation: Optional[str], 
                          company_data: Optional[Dict[str, Any]] = None, 
                          phase: str = 'current') -> List[str]:
        """
        将推荐结果映射到胜平负
        
        Args:
            recommendation: 推荐结果字符串
            company_data: 公司数据，用于特殊规则判断（如双平偏让平）
            phase: 阶段, 'initial' 或 'current'
            
        Returns:
            List[str]: 映射后的结果列表
        """
        if not recommendation:
            return []
        
        # 性能优化：移除频繁的debug日志，只在需要时记录
        # logger.debug(f"尝试映射推荐值: '{recommendation}' (phase: {phase})")
        
        # 特殊处理"双平偏让平"：根据规则值判断
        if recommendation == '双平偏让平' and company_data:
            # 根据阶段获取主客队规则值
            if phase == 'initial':
                home_rule = company_data.get('initial_home_rule_value', 999)
                away_rule = company_data.get('initial_away_rule_value', 999)
            else:  # current
                home_rule = company_data.get('current_home_rule_value', 999)
                away_rule = company_data.get('current_away_rule_value', 999)
            
            # 性能优化：移除频繁的debug日志
            # logger.debug(f"双平偏让平 - 主队规则值: {home_rule}, 客队规则值: {away_rule}")
            
            # 规则值小的一方获胜
            if home_rule < away_rule:
                return ['home_win']
            elif away_rule < home_rule:
                return ['away_win']
            else:
                return ['draw']
        
        # 查找映射规则
        if recommendation in self.recommendation_mapping:
            result = self.recommendation_mapping[recommendation]['result']
            # 性能优化：移除频繁的debug日志
            # logger.debug(f"找到映射: {recommendation} -> {result}")
            # 如果是列表，返回列表；如果是字符串，转为列表
            if isinstance(result, list):
                return result
            else:
                return [result]
        
        # 没有找到映射规则，只在DEBUG级别记录（避免频繁警告影响性能）
        logger.debug(f"未找到推荐值 '{recommendation}' 的映射规则，使用简单匹配")
        
        # 尝试简单匹配
        if 'home_win' in str(recommendation) or '主胜' in str(recommendation):
            return ['home_win']
        elif 'draw' in str(recommendation) or '平' in str(recommendation):
            return ['draw']
        elif 'away_win' in str(recommendation) or '客胜' in str(recommendation):
            return ['away_win']
        
        return []
    
    def calculate_company_summary(self, companies: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        计算公司推荐统计 - 分别统计初盘和即时盘
        
        Args:
            companies: 公司数据列表
            
        Returns:
            Dict[str, Any]: 包含统计结果的字典
        """
        # 性能优化：移除频繁的日志记录，只在DEBUG级别记录
        logger.debug(f"计算公司推荐统计，传入的公司数量: {len(companies)}")
        
        # 初始化统计结构
        summary = {
            'initial': {
                'home': {'count': 0.0, 'companies': []},
                'draw': {'count': 0.0, 'companies': []},
                'away': {'count': 0.0, 'companies': []},
                'total': 0
            },
            'current': {
                'home': {'count': 0.0, 'companies': []},
                'draw': {'count': 0.0, 'companies': []},
                'away': {'count': 0.0, 'companies': []},
                'total': 0
            },
            'total_companies': len(companies)
        }
        
        # 统计每个公司的推荐
        for idx, company in enumerate(companies):
            company_name = get_company_name_cn(company.get('company_id'), company.get('company_name'))
            
            # 性能优化：只在DEBUG级别记录样例数据
            if idx < 3:
                logger.debug(f"公司 {idx+1} 数据样例: company_id={company.get('company_id')}, "
                           f"initial_rec={company.get('initial_recommended_outcome')}, "
                           f"current_rec={company.get('current_recommended_outcome')}")
            
            # 统计初盘推荐
            initial_rec = company.get('initial_recommended_outcome')
            if initial_rec:
                mapped_results = self.map_recommendation(initial_rec, company, phase='initial')
                
                # 只有映射成功才计入统计
                if mapped_results:
                    summary['initial']['total'] += 1
                    
                    # 对于多个可能结果的情况（如"双平"），平均分配
                    weight = 1.0 / len(mapped_results) if len(mapped_results) > 0 else 0
                    
                    for result in mapped_results:
                        if result == 'home_win':
                            summary['initial']['home']['count'] += weight
                            if company_name not in summary['initial']['home']['companies']:
                                summary['initial']['home']['companies'].append(company_name)
                        elif result == 'draw':
                            summary['initial']['draw']['count'] += weight
                            if company_name not in summary['initial']['draw']['companies']:
                                summary['initial']['draw']['companies'].append(company_name)
                        elif result == 'away_win':
                            summary['initial']['away']['count'] += weight
                            if company_name not in summary['initial']['away']['companies']:
                                summary['initial']['away']['companies'].append(company_name)
            
            # 统计即时盘推荐
            current_rec = company.get('current_recommended_outcome')
            if current_rec:
                mapped_results = self.map_recommendation(current_rec, company, phase='current')
                
                # 只有映射成功才计入统计
                if mapped_results:
                    summary['current']['total'] += 1
                    
                    # 对于多个可能结果的情况（如"双平"），平均分配
                    weight = 1.0 / len(mapped_results) if len(mapped_results) > 0 else 0
                    
                    for result in mapped_results:
                        if result == 'home_win':
                            summary['current']['home']['count'] += weight
                            if company_name not in summary['current']['home']['companies']:
                                summary['current']['home']['companies'].append(company_name)
                        elif result == 'draw':
                            summary['current']['draw']['count'] += weight
                            if company_name not in summary['current']['draw']['companies']:
                                summary['current']['draw']['companies'].append(company_name)
                        elif result == 'away_win':
                            summary['current']['away']['count'] += weight
                            if company_name not in summary['current']['away']['companies']:
                                summary['current']['away']['companies'].append(company_name)
        
        # 先计算百分比，再处理用于显示的count整数值
        for phase in ['initial', 'current']:
            total = summary[phase]['total'] if summary[phase]['total'] > 0 else 1
            
            # 使用原始浮点数计算百分比
            summary[phase]['home']['percentage'] = round(summary[phase]['home']['count'] / total * 100, 1)
            summary[phase]['draw']['percentage'] = round(summary[phase]['draw']['count'] / total * 100, 1)
            summary[phase]['away']['percentage'] = round(summary[phase]['away']['count'] / total * 100, 1)
            
            # 将用于显示的count值四舍五入为整数
            summary[phase]['home']['count'] = round(summary[phase]['home']['count'])
            summary[phase]['draw']['count'] = round(summary[phase]['draw']['count'])
            summary[phase]['away']['count'] = round(summary[phase]['away']['count'])
        
        return summary


class MonitorIntervalCalculator:
    """监控间隔计算器"""
    
    @staticmethod
    def get_monitor_interval(match_time) -> Optional[int]:
        """
        根据比赛时间动态调整监控频率
        
        Args:
            match_time: 比赛时间
            
        Returns:
            Optional[int]: 监控间隔（秒），如果已开赛返回None
        """
        from config.monitoring_config import MONITOR_INTERVALS
        from datetime import datetime
        
        if isinstance(match_time, str):
            match_time = datetime.fromisoformat(match_time)
        
        time_to_match = (match_time - datetime.now()).total_seconds() / 60  # 转换为分钟
        
        # 注意：这个函数只用于scheduled状态的比赛
        # live和finished状态的比赛由update_monitor_frequency()中的状态逻辑处理
        if time_to_match <= 0:  # 理论上scheduled比赛不应该<=0，但防御性处理
            return MONITOR_INTERVALS['before_40m'] * 60  # 使用最高频率
        elif time_to_match <= 40:  # 开赛前40分钟
            return MONITOR_INTERVALS['before_40m'] * 60  # 转换为秒
        elif time_to_match <= 120:  # 开赛前2小时
            return MONITOR_INTERVALS['before_2h'] * 60
        elif time_to_match <= 480:  # 开赛前8小时
            return MONITOR_INTERVALS['before_8h'] * 60
        else:
            return MONITOR_INTERVALS['default'] * 60