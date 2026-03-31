#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
样本外验证服务（Out-of-Sample Validator）
用于在新数据库中验证策略规则的有效性
"""
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, date

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from app_database import execute_query, execute_update
from core.logger import get_logger
from validation_test.strategy_rule_service import StrategyRuleService

logger = get_logger(__name__)


class OutOfSampleValidator:
    """样本外验证器"""
    
    def __init__(self, 
                 validation_table: str = 'odds_analysis_results',
                 match_table: str = 'matches',
                 analysis_table: str = 'odds_analysis_results',
                 company_id: Optional[int] = None):
        """
        初始化验证器
        
        Args:
            validation_table: 验证数据表名（包含盘型信息的表）
            match_table: 比赛表名
            analysis_table: 分析结果表名（通常与validation_table相同）
            company_id: 公司ID（可选，如果指定则只验证该公司的数据）
        """
        self.validation_table = validation_table
        self.match_table = match_table
        self.analysis_table = analysis_table
        self.company_id = company_id
        self.rule_service = StrategyRuleService()
    
    def validate_rule(self, 
                     rule_id: int,
                     start_date: Optional[date] = None,
                     end_date: Optional[date] = None,
                     validation_database: Optional[str] = None) -> Dict[str, Any]:
        """
        验证单个策略规则
        
        Args:
            rule_id: 规则ID
            start_date: 验证开始日期（可选）
            end_date: 验证结束日期（可选）
            validation_database: 验证数据库名称（可选，用于记录）
            
        Returns:
            Dict: 验证结果
        """
        # 获取规则信息
        rule = self.rule_service.get_rule_by_id(rule_id)
        if not rule:
            raise ValueError(f"规则 ID {rule_id} 不存在")
        
        logger.info(f"开始验证规则 #{rule_id}: {rule['home_range_cond']} VS {rule['away_range_cond']} | 平:{rule['draw_range_cond']}")
        
        # 构建验证SQL
        sql = self._build_validation_sql(rule, start_date, end_date)
        params = self._build_validation_params(rule, start_date, end_date)
        
        # 执行验证查询
        results = execute_query(sql, params)
        
        if not results:
            logger.warning(f"规则 #{rule_id} 在新数据库中未找到匹配的比赛")
            return {
                'rule_id': rule_id,
                'total_matches': 0,
                'actual_wins': 0,
                'actual_draws': 0,
                'actual_losses': 0,
                'win_rate': 0.0,
                'unbeaten_rate': 0.0,
                'validation_status': 'NO_SAMPLE',
                'validation_comment': '样本过少，无法验证'
            }
        
        result = results[0]
        total = result['total_matches']
        wins = result['actual_wins']
        draws = result['actual_draws']
        losses = result['actual_losses']
        
        win_rate = (wins / total * 100) if total > 0 else 0.0
        unbeaten_rate = ((wins + draws) / total * 100) if total > 0 else 0.0
        
        # 判断验证状态
        validation_status, comment = self._determine_validation_status(
            win_rate, total, rule.get('training_win_rate', 0.0)
        )
        
        validation_result = {
            'rule_id': rule_id,
            'total_matches': total,
            'actual_wins': wins,
            'actual_draws': draws,
            'actual_losses': losses,
            'win_rate': round(win_rate, 2),
            'unbeaten_rate': round(unbeaten_rate, 2),
            'validation_status': validation_status,
            'validation_comment': comment
        }
        
        # 保存验证结果到数据库
        validation_id = self._save_validation_result(
            rule_id, validation_result, start_date, end_date, validation_database
        )
        validation_result['validation_id'] = validation_id
        
        # 更新规则的验证状态
        self.rule_service.update_validation_result(
            rule_id=rule_id,
            validation_status=validation_status,
            validation_sample_size=total,
            validation_win_rate=win_rate,
            validation_unbeaten_rate=unbeaten_rate
        )
        
        logger.info(f"规则 #{rule_id} 验证完成: {validation_status}, 胜率={win_rate:.1f}% ({wins}/{total})")
        
        return validation_result
    
    def _build_validation_sql(self, rule: Dict[str, Any], start_date: Optional[date], end_date: Optional[date]) -> str:
        """构建验证SQL查询"""
        # 使用子查询去重，确保每场比赛只计算一次（即使有多家公司的数据）
        sql = f"""
        SELECT 
            COUNT(*) AS total_matches,
            SUM(CASE WHEN home_score > away_score THEN 1 ELSE 0 END) AS actual_wins,
            SUM(CASE WHEN home_score = away_score THEN 1 ELSE 0 END) AS actual_draws,
            SUM(CASE WHEN home_score < away_score THEN 1 ELSE 0 END) AS actual_losses
        FROM (
            SELECT DISTINCT
                m.match_id,
                m.home_score,
                m.away_score
            FROM {self.match_table} m
            JOIN {self.analysis_table} a ON m.match_id = a.match_id
            WHERE m.match_status = 'finished'
              AND a.current_home_range = %s
              AND a.current_away_range = %s
              AND a.current_draw_range = %s
              AND m.home_score IS NOT NULL
              AND m.away_score IS NOT NULL
        """
        
        if self.company_id:
            sql += " AND a.company_id = %s"
        
        if start_date:
            sql += " AND DATE(m.match_time) >= %s"
        if end_date:
            sql += " AND DATE(m.match_time) <= %s"
        
        sql += " ) AS unique_matches"
        
        return sql
    
    def _build_validation_params(self, rule: Dict[str, Any], start_date: Optional[date], end_date: Optional[date]) -> Tuple:
        """构建验证SQL参数"""
        params = [
            rule['home_range_cond'],
            rule['away_range_cond'],
            rule['draw_range_cond']
        ]
        
        if self.company_id:
            params.append(self.company_id)
        
        if start_date:
            params.append(start_date)
        if end_date:
            params.append(end_date)
        
        return tuple(params)
    
    def _determine_validation_status(self, win_rate: float, sample_size: int, training_win_rate: float) -> Tuple[str, str]:
        """
        判断验证状态
        
        Returns:
            Tuple[str, str]: (validation_status, comment)
        """
        if sample_size < 3:
            return ('NO_SAMPLE', '样本过少，无法验证')
        
        if win_rate >= 0.75:
            return ('PASSED', '✅ 验证通过 (真理) - 胜率依然坚挺')
        elif win_rate >= 0.60:
            return ('WEAKENED', '⚠️ 效力减弱 (需谨慎) - 均值回归，但依然有效')
        else:
            return ('FAILED', '❌ 验证失败 (这是个巧合) - 过拟合，建议废弃')
    
    def _save_validation_result(self,
                               rule_id: int,
                               result: Dict[str, Any],
                               start_date: Optional[date],
                               end_date: Optional[date],
                               validation_database: Optional[str]) -> int:
        """保存验证结果到数据库"""
        sql = """
        INSERT INTO validation_results (
            rule_id, validation_database, validation_table,
            validation_start_date, validation_end_date,
            total_matches, actual_wins, actual_draws, actual_losses,
            win_rate, unbeaten_rate, validation_status, validation_comment
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        params = (
            rule_id,
            validation_database or 'default',
            self.validation_table,
            start_date,
            end_date,
            result['total_matches'],
            result['actual_wins'],
            result['actual_draws'],
            result['actual_losses'],
            result['win_rate'],
            result['unbeaten_rate'],
            result['validation_status'],
            result['validation_comment']
        )
        
        execute_update(sql, params)
        
        # 获取插入的ID
        validation_id_result = execute_query(
            "SELECT LAST_INSERT_ID() as validation_id"
        )
        return validation_id_result[0]['validation_id'] if validation_id_result else 0
    
    def validate_all_rules(self,
                          rule_ids: Optional[List[int]] = None,
                          start_date: Optional[date] = None,
                          end_date: Optional[date] = None,
                          validation_database: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        验证所有规则（或指定的规则列表）
        
        Args:
            rule_ids: 要验证的规则ID列表（None表示验证所有规则）
            start_date: 验证开始日期
            end_date: 验证结束日期
            validation_database: 验证数据库名称
            
        Returns:
            List[Dict]: 所有验证结果
        """
        if rule_ids:
            rules = [self.rule_service.get_rule_by_id(rid) for rid in rule_ids]
            rules = [r for r in rules if r]  # 过滤掉None
        else:
            rules = self.rule_service.get_all_rules()
        
        logger.info(f"开始验证 {len(rules)} 条策略规则...")
        
        results = []
        for rule in rules:
            try:
                result = self.validate_rule(
                    rule['rule_id'],
                    start_date=start_date,
                    end_date=end_date,
                    validation_database=validation_database
                )
                results.append(result)
            except Exception as e:
                logger.error(f"验证规则 #{rule['rule_id']} 时出错: {e}", exc_info=True)
                results.append({
                    'rule_id': rule['rule_id'],
                    'error': str(e)
                })
        
        return results
    
    def get_validation_report(self, validation_id: Optional[int] = None) -> Dict[str, Any]:
        """
        生成验证报告
        
        Args:
            validation_id: 验证ID（None表示生成所有验证的汇总报告）
            
        Returns:
            Dict: 验证报告
        """
        if validation_id:
            # 单个验证的详细报告
            sql = """
            SELECT 
                vr.*,
                sr.rule_name, sr.home_range_cond, sr.away_range_cond, sr.draw_range_cond,
                sr.expected_result, sr.training_win_rate, sr.rating
            FROM validation_results vr
            JOIN strategy_rules sr ON vr.rule_id = sr.rule_id
            WHERE vr.validation_id = %s
            """
            result = execute_query(sql, (validation_id,))
            if result:
                return result[0]
            return {}
        else:
            # 汇总报告
            sql = """
            SELECT 
                sr.rule_id,
                sr.rule_name,
                CONCAT(sr.home_range_cond, ' VS ', sr.away_range_cond, ' | 平:', sr.draw_range_cond) AS rule_desc,
                sr.training_win_rate AS training_win_rate,
                sr.training_sample_size AS training_sample_size,
                sr.validation_win_rate AS validation_win_rate,
                sr.validation_sample_size AS validation_sample_size,
                sr.validation_status,
                sr.rating,
                COUNT(vr.validation_id) AS validation_count,
                MAX(vr.validated_at) AS last_validated_at
            FROM strategy_rules sr
            LEFT JOIN validation_results vr ON sr.rule_id = vr.rule_id
            GROUP BY sr.rule_id
            ORDER BY sr.priority_order DESC, sr.rule_id
            """
            results = execute_query(sql)
            
            # 统计汇总
            total_rules = len(results)
            passed = sum(1 for r in results if r.get('validation_status') == 'PASSED')
            weakened = sum(1 for r in results if r.get('validation_status') == 'WEAKENED')
            failed = sum(1 for r in results if r.get('validation_status') == 'FAILED')
            pending = sum(1 for r in results if r.get('validation_status') == 'PENDING' or not r.get('validation_status'))
            
            return {
                'summary': {
                    'total_rules': total_rules,
                    'passed': passed,
                    'weakened': weakened,
                    'failed': failed,
                    'pending': pending
                },
                'rules': results
            }


if __name__ == '__main__':
    validator = OutOfSampleValidator()
    
    # 验证所有规则
    results = validator.validate_all_rules()
    
    # 生成报告
    report = validator.get_validation_report()
    
    print("\n" + "="*80)
    print("样本外验证报告")
    print("="*80)
    print(f"\n汇总统计:")
    print(f"  总规则数: {report['summary']['total_rules']}")
    print(f"  验证通过: {report['summary']['passed']}")
    print(f"  效力减弱: {report['summary']['weakened']}")
    print(f"  验证失败: {report['summary']['failed']}")
    print(f"  待验证: {report['summary']['pending']}")
    
    print(f"\n详细结果:\n")
    for rule in report['rules']:
        status_icon = {
            'PASSED': '✅',
            'WEAKENED': '⚠️',
            'FAILED': '❌',
            'PENDING': '⏳'
        }.get(rule.get('validation_status'), '❓')
        
        print(f"{status_icon} 规则 #{rule['rule_id']}: {rule['rule_desc']}")
        print(f"   训练胜率: {rule['training_win_rate']}% (样本: {rule['training_sample_size']})")
        if rule.get('validation_win_rate'):
            print(f"   验证胜率: {rule['validation_win_rate']}% (样本: {rule['validation_sample_size']})")
        print(f"   状态: {rule['validation_status']} | 评级: {rule['rating']}\n")
