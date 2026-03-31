#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赔率分析存储服务
负责将分析结果持久化到数据库
"""
import sys
from pathlib import Path
from typing import List, Dict, Tuple

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import DatabaseConnection
from core.logger import get_logger

class AnalysisStorageService:
    """
    负责处理赔率分析结果的数据库操作
    """
    def __init__(self, db: DatabaseConnection):
        self.db = db
        self.logger = get_logger(self.__class__.__name__)
        self._ensure_tables_exist()

    def save_analysis_results(self, match_id: int, results: List[Dict]):
        """批量保存分析结果
        
        修复：改用 UPSERT 逻辑（INSERT ON DUPLICATE KEY UPDATE），
        避免删除所有公司结果后只插入部分公司导致的数据丢失问题。
        原问题：某些公司因缺少广义实力数据而被跳过时，它们之前的分析结果也会被错误删除。
        """
        if not results:
            return
        
        # 清除相关缓存
        try:
            from utils.cache_invalidation import invalidate_analysis_cache
            invalidate_analysis_cache(match_id)
        except Exception as e:
            self.logger.warning(f"清除分析缓存失败: {e}")

        # 使用 UPSERT 逻辑：存在则更新，不存在则插入
        # 这样不会影响未被本次分析覆盖的公司的已有结果
        upsert_sql = """
            INSERT INTO odds_analysis_results (
                match_id, company_id, company_name,
                initial_home_fullwater, initial_draw_fullwater, initial_away_fullwater,
                current_home_fullwater, current_draw_fullwater, current_away_fullwater,
                home_power_level, away_power_level, power_diff,
                initial_home_theory_distance, initial_away_theory_distance,
                initial_home_offset, initial_away_offset,
                initial_home_range, initial_home_rule_value,
                initial_away_range, initial_away_rule_value,
                initial_rule_diff, initial_recommended_outcome, initial_confidence_level,
                current_home_theory_distance, current_away_theory_distance,
                current_home_offset, current_away_offset,
                current_home_range, current_home_rule_value,
                current_away_range, current_away_rule_value,
                current_rule_diff, current_recommended_outcome, current_confidence_level,
                initial_draw_standard, initial_draw_range,
                current_draw_standard, current_draw_range,
                analyzed_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                      %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 
                      %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                company_name = VALUES(company_name),
                initial_home_fullwater = VALUES(initial_home_fullwater),
                initial_draw_fullwater = VALUES(initial_draw_fullwater),
                initial_away_fullwater = VALUES(initial_away_fullwater),
                current_home_fullwater = VALUES(current_home_fullwater),
                current_draw_fullwater = VALUES(current_draw_fullwater),
                current_away_fullwater = VALUES(current_away_fullwater),
                home_power_level = VALUES(home_power_level),
                away_power_level = VALUES(away_power_level),
                power_diff = VALUES(power_diff),
                initial_home_theory_distance = VALUES(initial_home_theory_distance),
                initial_away_theory_distance = VALUES(initial_away_theory_distance),
                initial_home_offset = VALUES(initial_home_offset),
                initial_away_offset = VALUES(initial_away_offset),
                initial_home_range = VALUES(initial_home_range),
                initial_home_rule_value = VALUES(initial_home_rule_value),
                initial_away_range = VALUES(initial_away_range),
                initial_away_rule_value = VALUES(initial_away_rule_value),
                initial_rule_diff = VALUES(initial_rule_diff),
                initial_recommended_outcome = VALUES(initial_recommended_outcome),
                initial_confidence_level = VALUES(initial_confidence_level),
                current_home_theory_distance = VALUES(current_home_theory_distance),
                current_away_theory_distance = VALUES(current_away_theory_distance),
                current_home_offset = VALUES(current_home_offset),
                current_away_offset = VALUES(current_away_offset),
                current_home_range = VALUES(current_home_range),
                current_home_rule_value = VALUES(current_home_rule_value),
                current_away_range = VALUES(current_away_range),
                current_away_rule_value = VALUES(current_away_rule_value),
                current_rule_diff = VALUES(current_rule_diff),
                current_recommended_outcome = VALUES(current_recommended_outcome),
                current_confidence_level = VALUES(current_confidence_level),
                initial_draw_standard = VALUES(initial_draw_standard),
                initial_draw_range = VALUES(initial_draw_range),
                current_draw_standard = VALUES(current_draw_standard),
                current_draw_range = VALUES(current_draw_range),
                analyzed_at = NOW()
        """
        
        params_list = self._prepare_data_for_save(match_id, results)
        
        try:
            self.db.execute_many(upsert_sql, params_list)
            self.logger.info(f"成功为比赛 {match_id} 保存/更新了 {len(results)} 条分析结果")
        except Exception as e:
            self.logger.error(f"批量保存比赛 {match_id} 的分析结果失败: {e}", exc_info=True)

    def _prepare_data_for_save(self, match_id: int, results: List[Dict]) -> List[Tuple]:
        """将分析结果字典列表转换为元组列表以供 executemany 使用"""
        params = []
        for res in results:
            ia = res['initial_analysis']
            ca = res['current_analysis']
            da = res['draw_analysis']
            params.append((
                match_id, res['company_id'], res['company_name'],
                res['initial_home'], res['initial_draw'], res['initial_away'],
                res['current_home'], res['current_draw'], res['current_away'],
                res['home_power'], res['away_power'], res['power_diff'],
                ia['home_theory_distance'], ia['away_theory_distance'],
                ia['home_offset'], ia['away_offset'],
                ia['home_rule']['description'], ia['home_rule']['rule_value'],
                ia['away_rule']['description'], ia['away_rule']['rule_value'],
                ia['rule_diff'], ia['recommendation']['outcome'], ia['recommendation']['confidence'],
                ca['home_theory_distance'], ca['away_theory_distance'],
                ca['home_offset'], ca['away_offset'],
                ca['home_rule']['description'], ca['home_rule']['rule_value'],
                ca['away_rule']['description'], ca['away_rule']['rule_value'],
                ca['rule_diff'], ca['recommendation']['outcome'], ca['recommendation']['confidence'],
                da['initial_standard_draw'], da['initial_draw_range'],
                da['current_standard_draw'], da['current_draw_range']
            ))
        return params

    def _ensure_tables_exist(self):
        """确保分析结果表存在"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS odds_analysis_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            company_id INT NOT NULL,
            company_name VARCHAR(100),
            
            initial_home_fullwater DECIMAL(10,4),
            initial_draw_fullwater DECIMAL(10,4),
            initial_away_fullwater DECIMAL(10,4),
            current_home_fullwater DECIMAL(10,4),
            current_draw_fullwater DECIMAL(10,4),
            current_away_fullwater DECIMAL(10,4),
            
            home_power_level DECIMAL(10,4),
            away_power_level DECIMAL(10,4),
            power_diff DECIMAL(10,4),
            
            initial_home_theory_distance DECIMAL(10,4),
            initial_away_theory_distance DECIMAL(10,4),
            initial_home_offset DECIMAL(10,4),
            initial_away_offset DECIMAL(10,4),
            initial_home_range VARCHAR(50),
            initial_home_rule_value INT,
            initial_away_range VARCHAR(50),
            initial_away_rule_value INT,
            initial_rule_diff INT,
            initial_recommended_outcome VARCHAR(20),
            initial_confidence_level VARCHAR(10),
            
            current_home_theory_distance DECIMAL(10,4),
            current_away_theory_distance DECIMAL(10,4),
            current_home_offset DECIMAL(10,4),
            current_away_offset DECIMAL(10,4),
            current_home_range VARCHAR(50),
            current_home_rule_value INT,
            current_away_range VARCHAR(50),
            current_away_rule_value INT,
            current_rule_diff INT,
            current_recommended_outcome VARCHAR(20),
            current_confidence_level VARCHAR(10),
            
            initial_draw_standard DECIMAL(10,4),
            initial_draw_range VARCHAR(20),
            current_draw_standard DECIMAL(10,4),
            current_draw_range VARCHAR(20),
            
            analyzed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            
            UNIQUE KEY uk_match_company (match_id, company_id),
            INDEX idx_analyzed (analyzed_at)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        try:
            self.db.execute_query(create_table_sql, fetch=None)
            self.logger.info("分析结果表 `odds_analysis_results` 已准备就绪")
        except Exception as e:
            self.logger.error(f"创建 `odds_analysis_results` 表失败: {e}")
 