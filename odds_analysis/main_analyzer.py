#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
新版赔率分析主入口
"""
import sys
from pathlib import Path
import argparse
import logging
import time
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger, setup_logging
from odds_analysis.analysis_repository import AnalysisRepository
from odds_analysis.analysis_service import AnalysisService
from odds_analysis.analysis_storage import AnalysisStorageService
from odds_analysis.analysis_presenter import AnalysisPresenter

logger = get_logger(__name__)

class MainAnalyzer:
    """
    总指挥：协调数据、服务、存储和展示层
    """
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.db = get_connection()
        self.repository = AnalysisRepository(self.db)
        self.storage_service = AnalysisStorageService(self.db)
        
        # 加载所有规则和参照表
        self.logger.info("正在加载赔率分析所需的规则和参照表...")
        standard_odds_win, standard_odds_loss = self.repository.get_standard_odds()
        rule_conditions_home, rule_conditions_away = self.repository.get_rule_conditions()
        rule_outcomes = self.repository.get_rule_outcomes()
        
        self.analysis_service = AnalysisService(
            standard_odds_win,
            standard_odds_loss,
            rule_conditions_home,
            rule_conditions_away,
            rule_outcomes
        )
        self.logger.info("分析服务已成功初始化。")

    def analyze_match(self, match_id: int):
        """分析单场比赛"""
        self.logger.info(f"开始分析比赛ID: {match_id}")
        
        match_info = self.repository.get_match_info(match_id)
        if not match_info:
            self.logger.error(f"无法找到比赛 {match_id} 的信息")
            return

        # [关键修复] 检查比赛状态，已结束的比赛不应该再进行分析
        match_status = match_info.get('match_status')
        if match_status == 'finished':
            self.logger.warning(
                f"比赛 {match_id} 状态为 'finished'（已结束），跳过分析。"
                f"比赛时间: {match_info.get('match_time')}"
            )
            return

        # 数据源优先：odds_changes；若无数据且允许回退，则回退至 european_odds
        preferred_source = getattr(self, 'data_source', 'odds_changes')
        all_odds = []
        if preferred_source == 'odds_changes':
            all_odds = self.repository.get_latest_odds_for_match(match_id)
            if not all_odds:
                self.logger.warning(f"odds_changes 无数据，自动回退到 european_odds（只在验证/补数场景）。")
                all_odds = self.repository.get_latest_odds_from_european(match_id)
        else:
            all_odds = self.repository.get_latest_odds_from_european(match_id)
        if not all_odds:
            self.logger.warning(f"比赛 {match_id} 没有任何赔率数据")
            return

        power_ratings = self.repository.get_team_powers_for_companies(
            [o['company_id'] for o in all_odds],
            match_info['home_team_id'],
            match_info['away_team_id'],
            league_id=match_info.get('league_id'),
            division=match_info.get('division')
        )
        
        self.logger.info(f"为 {len(power_ratings)} 家公司找到了匹配的广义实力数据")

        # [修正] 放宽对广义实力的强依赖，特别是在联赛初期
        odds_with_power = {}
        for o in all_odds:
            company_id = o['company_id']
            # 即使没有广义实力数据，也先创建一个基础记录
            odds_with_power[company_id] = o.copy()
            
            if company_id in power_ratings:
                # 如果有实力数据，则合并
                odds_with_power[company_id].update(power_ratings[company_id])
            else:
                # 如果没有实力数据
                # 检查是否为联赛初期（前4轮），如果是，则使用默认值继续分析
                round_number = match_info.get('round_number')
                # 如果 round_number 为 None 或 <= 4，都使用默认值继续分析（避免澳超等联赛因 round_number 为 None 而全部跳过）
                if round_number is None or round_number <= 4:
                    round_info = f"第 {round_number} 轮" if round_number is not None else "轮次未知"
                    self.logger.warning(f"联赛初期或轮次未知 ({round_info}): 公司 {company_id} 缺少广义实力数据，使用默认值继续分析。")
                    # 提供安全的默认值
                    odds_with_power[company_id].update({
                        'home_power': None,
                        'away_power': None,
                        'power_diff': 0.0  # 关键：设置默认实力差为0
                    })
                else:
                    # 如果不是联赛初期（> 4轮），则跳过这家公司
                    self.logger.warning(f"非联赛初期 (第 {round_number} 轮): 公司 {company_id} 缺少广义实力数据，跳过分析。")
                    del odds_with_power[company_id] # 移除没有实力数据的记录

        valid_results = []
        for company_id, odds_data in odds_with_power.items():
            # 确保 power_diff 存在，即使是默认值
            power_diff = odds_data.get('power_diff')
            if power_diff is None:
                continue # 如果经过上述逻辑仍然没有实力差，则跳过
            
            # AnalysisService 自己处理规则匹配，不需要外部传入规则
            result = self.analysis_service.analyze_company_odds(
                odds_data,
                power_diff
            )
            
            if result:
                valid_results.append(result)

        if valid_results:
            self.storage_service.save_analysis_results(match_id, valid_results)
            self.logger.info(f"为比赛 {match_id} 生成了 {len(valid_results)} 条有效分析结果并已存储。")
        else:
            print(f"比赛 {match_id} 没有生成有效的分析结果。")
        
        self.logger.info(f"比赛 {match_id} 分析完成。")

    def close(self):
        self.repository.close()
        self.db.close()


def main():
    """主函数，执行赔率分析"""
    # 设置日志记录
    setup_logging()

    logger = logging.getLogger(__name__)

    try:
        parser = argparse.ArgumentParser(description="新版赔率分析工具")
        parser.add_argument('match_id', type=int, help='需要分析的比赛ID')
        
        args = parser.parse_args()
        
        analyzer = MainAnalyzer()
        analyzer.analyze_match(args.match_id)
    except Exception as e:
        # 确保即使在主逻辑之外出错也能被捕获
        logging.getLogger(__name__).error(f"程序启动失败: {e}", exc_info=True)


if __name__ == "__main__":
    main()
 