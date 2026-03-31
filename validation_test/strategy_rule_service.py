#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
策略规则管理服务
负责策略规则的CRUD操作
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from app_database import execute_query, execute_update
from core.logger import get_logger

logger = get_logger(__name__)


class StrategyRuleService:
    """策略规则管理服务"""
    
    def __init__(self):
        self._ensure_tables_exist()
    
    def _ensure_tables_exist(self):
        """确保策略规则表存在"""
        try:
            sql_file = Path(__file__).parent / 'strategy_rules.sql'
            if sql_file.exists():
                with open(sql_file, 'r', encoding='utf-8') as f:
                    sql_content = f.read()
                    # 分割SQL语句（按分号和换行）
                    statements = [s.strip() for s in sql_content.split(';') if s.strip() and not s.strip().startswith('--')]
                    for statement in statements:
                        if statement:
                            try:
                                execute_update(statement)
                            except Exception as e:
                                # 表可能已存在，忽略错误
                                logger.debug(f"执行SQL语句时出错（可能表已存在）: {e}")
                logger.info("策略规则表已准备就绪")
        except Exception as e:
            logger.warning(f"创建策略规则表时出错: {e}")
    
    def create_rule(self, 
                    home_range_cond: str,
                    away_range_cond: str,
                    draw_range_cond: str,
                    expected_result: str,
                    rule_name: Optional[str] = None,
                    priority_order: int = 0,
                    training_sample_size: int = 0,
                    training_win_rate: float = 0.0,
                    training_unbeaten_rate: float = 0.0,
                    rating: str = 'N/A') -> int:
        """
        创建策略规则
        
        Args:
            home_range_cond: 主队盘型条件
            away_range_cond: 客队盘型条件
            draw_range_cond: 平局盘型条件
            expected_result: 期望结果（HOME_WIN, AWAY_WIN, DRAW）
            rule_name: 规则名称
            priority_order: 优先级
            training_sample_size: 训练样本数
            training_win_rate: 训练集胜率
            training_unbeaten_rate: 训练集不败率
            rating: 评级
            
        Returns:
            int: 创建的规则ID
        """
        sql = """
        INSERT INTO strategy_rules (
            home_range_cond, away_range_cond, draw_range_cond, expected_result,
            rule_name, priority_order, training_sample_size, 
            training_win_rate, training_unbeaten_rate, rating
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            rule_name = VALUES(rule_name),
            priority_order = VALUES(priority_order),
            training_sample_size = VALUES(training_sample_size),
            training_win_rate = VALUES(training_win_rate),
            training_unbeaten_rate = VALUES(training_unbeaten_rate),
            rating = VALUES(rating),
            updated_at = NOW()
        """
        
        params = (
            home_range_cond, away_range_cond, draw_range_cond, expected_result,
            rule_name, priority_order, training_sample_size,
            training_win_rate, training_unbeaten_rate, rating
        )
        
        try:
            execute_update(sql, params)
            # 获取插入的ID
            result = execute_query(
                "SELECT rule_id FROM strategy_rules WHERE home_range_cond = %s AND away_range_cond = %s AND draw_range_cond = %s AND expected_result = %s",
                (home_range_cond, away_range_cond, draw_range_cond, expected_result)
            )
            if result:
                rule_id = result[0]['rule_id']
                logger.info(f"成功创建/更新策略规则 ID={rule_id}: {home_range_cond} VS {away_range_cond} | 平:{draw_range_cond}")
                return rule_id
        except Exception as e:
            logger.error(f"创建策略规则失败: {e}", exc_info=True)
            raise
        
        return 0
    
    def batch_create_rules(self, rules: List[Dict[str, Any]]) -> int:
        """
        批量创建策略规则
        
        Args:
            rules: 规则列表，每个规则包含 home_range_cond, away_range_cond, draw_range_cond, expected_result 等字段
            
        Returns:
            int: 成功创建的规则数量
        """
        count = 0
        for rule in rules:
            try:
                self.create_rule(
                    home_range_cond=rule['home_range_cond'],
                    away_range_cond=rule['away_range_cond'],
                    draw_range_cond=rule['draw_range_cond'],
                    expected_result=rule.get('expected_result', 'HOME_WIN'),
                    rule_name=rule.get('rule_name'),
                    priority_order=rule.get('priority_order', 0),
                    training_sample_size=rule.get('training_sample_size', 0),
                    training_win_rate=rule.get('training_win_rate', 0.0),
                    training_unbeaten_rate=rule.get('training_unbeaten_rate', 0.0),
                    rating=rule.get('rating', 'N/A')
                )
                count += 1
            except Exception as e:
                logger.error(f"批量创建规则时出错: {e}")
        
        logger.info(f"批量创建策略规则完成: {count}/{len(rules)}")
        return count
    
    def get_all_rules(self, validation_status: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        获取所有策略规则
        
        Args:
            validation_status: 过滤验证状态（可选）
            
        Returns:
            List[Dict]: 策略规则列表
        """
        if validation_status:
            sql = "SELECT * FROM strategy_rules WHERE validation_status = %s ORDER BY priority_order DESC, rule_id"
            return execute_query(sql, (validation_status,))
        else:
            sql = "SELECT * FROM strategy_rules ORDER BY priority_order DESC, rule_id"
            return execute_query(sql)
    
    def get_rule_by_id(self, rule_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取策略规则"""
        sql = "SELECT * FROM strategy_rules WHERE rule_id = %s"
        result = execute_query(sql, (rule_id,))
        return result[0] if result else None
    
    def update_validation_result(self, 
                                 rule_id: int,
                                 validation_status: str,
                                 validation_sample_size: int,
                                 validation_win_rate: float,
                                 validation_unbeaten_rate: float = 0.0):
        """
        更新规则的验证结果
        
        Args:
            rule_id: 规则ID
            validation_status: 验证状态（PASSED, WEAKENED, FAILED）
            validation_sample_size: 验证样本数
            validation_win_rate: 验证胜率
            validation_unbeaten_rate: 验证不败率
        """
        sql = """
        UPDATE strategy_rules 
        SET validation_status = %s,
            validation_sample_size = %s,
            validation_win_rate = %s,
            validation_unbeaten_rate = %s,
            last_validated_at = NOW(),
            updated_at = NOW()
        WHERE rule_id = %s
        """
        
        execute_update(sql, (validation_status, validation_sample_size, 
                            validation_win_rate, validation_unbeaten_rate, rule_id))
        logger.info(f"更新规则 {rule_id} 的验证结果: {validation_status}, 胜率={validation_win_rate}%")
    
    def import_verified_rules(self):
        """
        导入经 过拟合验证 的高置信度规则
        """
        verified_rules = [
            # 1. 必杀主胜 (验证结果: 100% 胜率)
            {
                'home_range_cond': '超实盘高水',
                'away_range_cond': '韬光盘低水',
                'draw_range_cond': '任意',  # 暂不限制平赔
                'expected_result': 'HOME_WIN',
                'rule_name': '【验证确信】超实高水杀韬光',
                'priority_order': 200,
                'training_sample_size': 11,
                'training_win_rate': 90.9,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★★★'
            },
            # 2. 稳健主不败 (验证结果: 100% 不败)
            {
                'home_range_cond': '实开盘低水',
                'away_range_cond': '实开盘超高水',
                'draw_range_cond': '任意',
                'expected_result': 'HOME_1X',
                'rule_name': '【验证确信】实开低水防守稳',
                'priority_order': 190,
                'training_sample_size': 11,
                'training_win_rate': 63.6,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★★'
            },
            # 3. 稳健收米 (验证结果: 100% 不败)
            {
                'home_range_cond': '实开盘超低水',
                'away_range_cond': '高开盘中高水',
                'draw_range_cond': '任意',
                'expected_result': 'HOME_1X',
                'rule_name': '【验证确信】实开超低稳胆',
                'priority_order': 180,
                'training_sample_size': 8,
                'training_win_rate': 87.5,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★★'
            },
            # 4. 韬光低水必死 (验证结果: 100% 不败)
            {
                'home_range_cond': '实开盘低水',
                'away_range_cond': '韬光盘低水',
                'draw_range_cond': '任意',
                'expected_result': 'HOME_1X',
                'rule_name': '【验证确信】实开低水克韬光',
                'priority_order': 170,
                'training_sample_size': 16,
                'training_win_rate': 68.8,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★★'
            }
        ]
        
        count = self.batch_create_rules(verified_rules)
        logger.info(f"成功导入 {count} 条验证确信规则")
        return count


    def import_golden_rules(self):
        """
        导入用户提供的"黄金定式"规则
        根据用户提供的数据自动创建规则
        """
        # 完美定式（100%胜率，样本≥5）
        perfect_rules = [
            {
                'home_range_cond': '超实盘中水',
                'away_range_cond': '韬光盘中低水',
                'draw_range_cond': '平实高',
                'expected_result': 'HOME_WIN',
                'rule_name': '完美定式 #1',
                'priority_order': 100,
                'training_sample_size': 10,
                'training_win_rate': 100.0,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★★'
            },
            {
                'home_range_cond': '低开盘中高水',
                'away_range_cond': '高开盘中低水',
                'draw_range_cond': '平中庸上',
                'expected_result': 'HOME_WIN',
                'rule_name': '完美定式 #2',
                'priority_order': 99,
                'training_sample_size': 5,
                'training_win_rate': 100.0,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★★'
            },
        ]
        
        # 高胜定式（80-89%，样本≥5）
        high_win_rules = [
            {
                'home_range_cond': '低开盘中低水',
                'away_range_cond': '韬光盘低水',
                'draw_range_cond': '平实低',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #1',
                'priority_order': 80,
                'training_sample_size': 8,
                'training_win_rate': 87.5,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '实开盘超低水',
                'away_range_cond': '实开盘超高水',
                'draw_range_cond': '平中庸下',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #2',
                'priority_order': 79,
                'training_sample_size': 7,
                'training_win_rate': 85.7,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '实开盘中高水',
                'away_range_cond': '实开盘中水',
                'draw_range_cond': '低开平',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #3',
                'priority_order': 78,
                'training_sample_size': 7,
                'training_win_rate': 85.7,
                'training_unbeaten_rate': 85.7,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '实开盘中高水',
                'away_range_cond': '实开盘超低水',
                'draw_range_cond': '高开平',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #4',
                'priority_order': 77,
                'training_sample_size': 7,
                'training_win_rate': 85.7,
                'training_unbeaten_rate': 85.7,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '低开盘中低水',
                'away_range_cond': '高开盘中高水',
                'draw_range_cond': '平实高',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #5',
                'priority_order': 76,
                'training_sample_size': 7,
                'training_win_rate': 85.7,
                'training_unbeaten_rate': 85.7,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '超实盘中水',
                'away_range_cond': '韬光盘低水',
                'draw_range_cond': '高开平',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #6',
                'priority_order': 75,
                'training_sample_size': 6,
                'training_win_rate': 83.3,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '实开盘高水',
                'away_range_cond': '实开盘低水',
                'draw_range_cond': '平实高',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #7',
                'priority_order': 74,
                'training_sample_size': 6,
                'training_win_rate': 83.3,
                'training_unbeaten_rate': 100.0,
                'rating': '★★★★'
            },
            {
                'home_range_cond': '实开盘中高水',
                'away_range_cond': '实开盘超高水',
                'draw_range_cond': '低开平',
                'expected_result': 'HOME_WIN',
                'rule_name': '高胜定式 #8',
                'priority_order': 73,
                'training_sample_size': 10,
                'training_win_rate': 80.0,
                'training_unbeaten_rate': 90.0,
                'rating': '★★★'
            },
        ]
        
        all_rules = perfect_rules + high_win_rules
        count = self.batch_create_rules(all_rules)
        logger.info(f"成功导入 {count} 条黄金定式规则")
        return count


if __name__ == '__main__':
    service = StrategyRuleService()
    service.import_golden_rules()
    rules = service.get_all_rules()
    print(f"\n共找到 {len(rules)} 条策略规则：\n")
    for rule in rules:
        print(f"规则 #{rule['rule_id']}: {rule['home_range_cond']} VS {rule['away_range_cond']} | 平:{rule['draw_range_cond']}")
        print(f"  期望结果: {rule['expected_result']}, 训练胜率: {rule['training_win_rate']}%, 评级: {rule['rating']}\n")
