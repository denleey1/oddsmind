#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MySQL版广义实力计算器 - 适配OddsMind数据库结构
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger
import pandas as pd
from datetime import datetime, timedelta
import numpy as np
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from calculation.strength_repository import StrengthDataRepository
from calculation.strength_service import StrengthCalculationService
from calculation.strength_storage import StrengthStorageService
from calculation.strength_presenter import StrengthResultPresenter

logger = get_logger(__name__)

# 数据完整性阈值 - 与原版保持一致
MISSING_ODDS_THRESHOLD = 5.0  # 5% missing rate threshold

class MySQLGeneralStrengthCalculator:
    """基于MySQL OddsMind数据库的广义实力计算器"""
    
    def __init__(self, league_id: int, season: Optional[str] = None,
                 target_round: Optional[int] = None, start_round: Optional[int] = None,
                 division: Optional[str] = None):
        """
        初始化计算器
        
        Args:
            league_id: 联赛ID (36=英超, 31=西甲, 8=德甲等)
            season: 赛季 (如 "2024-25")
            target_round: 目标轮次 (如果指定，只计算到该轮次结束后的实力)
            start_round: 起始轮次 (如果指定，只计算从该轮次开始的比赛)
            division: 分区标识 (如 'east', 'west')。为 None 表示全局计算。
        """
        self.league_id = league_id
        self.season = season
        self.target_round = target_round
        self.start_round = start_round
        self.division = division
        self.db = get_connection()
        self.repository = StrengthDataRepository(self.db)
        self.service = StrengthCalculationService()
        # Storage 和 Presenter 在每个线程中单独实例化
        
        self.league_info = None
        self._print_lock = threading.Lock()

    def calculate(self, max_workers: int = 12) -> Dict[str, object]:
        """
        并行计算联赛下所有符合条件的公司的广义实力
        """
        div_label = f" [分区={self.division}]" if self.division else ""
        summary: Dict[str, object] = {
            'league_id': self.league_id,
            'division': self.division or '',
            'status': 'ok',
            'total_companies': 0,
            'succeeded_companies': 0,
            'failed_companies': 0,
            'errors': {},
        }

        logger.info("=" * 60)
        logger.info(f"开始为联赛ID {self.league_id}{div_label} 进行广义实力并行计算")
        logger.info("=" * 60)

        # 1. 加载联赛信息
        self.league_info = self.repository.get_league_info(self.league_id)
        if not self.league_info:
            summary['status'] = 'error'
            summary['errors'] = {'league': f'未找到联赛ID {self.league_id} 的信息'}
            return summary
            
        # 2. 加载所有符合条件的公司数据（带分区过滤）
        companies_data_map = self.repository.load_all_companies_data(
            self.league_id, self.season, division=self.division
        )
        if not companies_data_map:
            logger.warning(f"联赛 {self.league_id}{div_label} 没有找到任何满足数据覆盖率的公司，计算中止。")
            summary['status'] = 'skipped'
            summary['errors'] = {'companies': '没有满足覆盖率阈值的数据'}
            return summary
             
        logger.info(f"共找到 {len(companies_data_map)} 家符合条件的公司，准备开始并行计算...")
        summary['total_companies'] = len(companies_data_map)
        failed_errors: Dict[int, str] = {}

        # 3. 使用线程池并行处理
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._calculate_for_company, company_id, company_df): company_id
                for company_id, company_df in companies_data_map.items()
            }

            for future in as_completed(futures):
                company_id = futures[future]
                try:
                    future.result()
                    summary['succeeded_companies'] = int(summary['succeeded_companies']) + 1
                    logger.info(f"✅ 公司ID {company_id} 的计算任务成功完成。")
                except Exception as e:
                    summary['failed_companies'] = int(summary['failed_companies']) + 1
                    failed_errors[company_id] = str(e)
                    logger.error(f"❌ 公司ID {company_id} 的计算任务失败: {e}", exc_info=True)
        
        if summary['failed_companies']:
            summary['status'] = 'partial'
        summary['errors'] = failed_errors

        logger.info("=" * 60)
        logger.info(f"联赛ID {self.league_id} 的所有计算任务已完成。")
        logger.info("=" * 60)
        return summary
        
    def _calculate_for_company(self, company_id: int, matches_df: pd.DataFrame):
        """
        为单个公司执行计算、存储和显示的完整流程
        """
        company_name = matches_df['company_name'].iloc[0]
        div_label = f" [分区={self.division}]" if self.division else ""
        logger.info(f"--- 开始处理公司: {company_name} (ID: {company_id}){div_label} ---")

        # 1. 实例化当前线程所需的服务
        storage = StrengthStorageService(self.db, self.league_id)
        presenter = StrengthResultPresenter()

        # 2. 核心计算
        team_powers, current_round = self.service.calculate_all_teams_strength(matches_df)
        if not team_powers:
            raise ValueError("计算服务未能返回实力结果。")
            
        # 3. 确定用于显示的轮次 (解决部分完成轮次的歧义问题)
        display_round = current_round
        if current_round is not None and current_round > 1:
            # 通过比较最新一轮和倒数第二轮的比赛场数，来判断最新一轮是否完整
            unique_rounds = sorted(matches_df['round_number'].unique())
            if len(unique_rounds) > 1:
                penultimate_round_number = unique_rounds[-2]
                
                matches_in_penultimate_round = (matches_df['round_number'] == penultimate_round_number).sum()
                matches_in_current_round = (matches_df['round_number'] == current_round).sum()
                
                # 如果最新轮次的比赛数少于上一轮，则认为它未完成
                if matches_in_current_round < matches_in_penultimate_round:
                    display_round = current_round - 1
                    logger.info(
                        f"最新轮次 {current_round} 比赛不完整 ({matches_in_current_round}/{matches_in_penultimate_round} 场), "
                        f"显示轮次将使用: {display_round}"
                    )
            
        # 4. 存储结果 (存储时必须使用真实的最新轮次)
        storage.save_results(
            team_powers=team_powers,
            league_info=self.league_info,
            company_id=company_id,
            company_name=company_name,
            season=self.season,
            start_round=self.start_round,
            target_round=current_round,
            division=self.division or ''
        )

        # 5. 展示结果 (展示时使用我们计算出的、无歧义的轮次)
        with self._print_lock:
            presenter.display(
                team_powers=team_powers,
                league_info=self.league_info,
                company_name=company_name,
                target_round=display_round,
                division=self.division
            )
        logger.info(f"--- 公司: {company_name} (ID: {company_id}){div_label} 处理完毕 ---")
    
    def display_results(self):
        """
        显示计算结果
        """
        if not self.team_powers:
            logger.warning("没有计算结果可显示")
            return

        company_name = self.matches_df['company_name'].iloc[0] if 'company_name' in self.matches_df.columns else '未知公司'
        self.presenter.display(
            team_powers=self.team_powers,
            league_info=self.league_info,
            company_name=company_name,
            target_round=self.target_round
        )
    
    def get_results_dataframe(self) -> pd.DataFrame:
        """
        获取计算结果的DataFrame格式，用于显示
        
        Returns:
            结果DataFrame
        """
        if not self.team_powers:
            logger.warning("没有计算结果")
            return pd.DataFrame()
        
        results_df = pd.DataFrame.from_dict(self.team_powers, orient='index')
        results_df = results_df.sort_values('relative_power', ascending=False)  # 按相对实力排序
        results_df.reset_index(inplace=True)
        results_df.rename(columns={'index': 'team_id'}, inplace=True)
        
        # 添加排名列
        results_df['rank'] = range(1, len(results_df) + 1)
        
        return results_df


def run_league_calculation(league_id: int, season: Optional[str], start_round: Optional[int],
                           target_round: Optional[int], division: Optional[str] = None):
    """
    为单个联赛（或联赛的某个分区）执行计算任务的独立函数，便于并行调用
    """
    div_label = f" [分区={division}]" if division else ""
    try:
        calculator = MySQLGeneralStrengthCalculator(
            league_id=league_id,
            season=season,
            target_round=target_round,
            start_round=start_round,
            division=division
        )
        calculator.calculate()
    except Exception as e:
        logger.error(f"处理联赛ID {league_id}{div_label} 时发生未知错误: {e}", exc_info=True)


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="MySQL广义实力并行计算器")
    parser.add_argument('--league-ids', type=str, required=False,
                       help='需要计算的联赛ID列表，用逗号分隔 (例如: 25,36,31)')
    parser.add_argument('--all-leagues', action='store_true',
                       help='如果指定此参数，将自动计算数据库中所有符合条件的联赛')
    parser.add_argument('--season', type=str, help='赛季 (如 2024-25)')
    parser.add_argument('--target-round', type=int, help='目标轮次 (只计算到该轮次结束后的实力)')
    parser.add_argument('--start-round', type=int, help='起始轮次 (只计算从该轮次开始的比赛)')
    parser.add_argument('--max-league-workers', type=int, default=4, 
                       help='用于并行处理不同联赛的最大线程数')
    
    args = parser.parse_args()
    
    league_ids = []
    if args.all_leagues:
        logger.info("正在自动获取所有联赛ID...")
        try:
            db_conn = get_connection()
            leagues_data = db_conn.execute_query(
                "SELECT DISTINCT league_id FROM matches WHERE match_status = 'finished' ORDER BY league_id",
                fetch='all'
            )
            if leagues_data:
                league_ids = [row['league_id'] for row in leagues_data]
                logger.info(f"成功获取到 {len(league_ids)} 个联赛，准备开始计算...")
            else:
                logger.error("未能从数据库获取到任何联赛ID。")
                return
        except Exception as e:
            logger.error(f"从数据库自动获取联赛ID时发生错误: {e}", exc_info=True)
            return
    elif args.league_ids:
        try:
            league_ids = [int(lid.strip()) for lid in args.league_ids.split(',')]
        except ValueError:
            logger.error("无法解析 --league-ids 参数，请确保是逗号分隔的数字。")
            return
    else:
        parser.error("必须提供 --league-ids 或 --all-leagues 参数中的一个。")
        return
        
    logger.info(f"准备为联赛 {league_ids} 启动并行计算...")
    logger.info(f"最大联赛并发数: {args.max_league_workers}")
    
    with ThreadPoolExecutor(max_workers=args.max_league_workers) as executor:
        futures = {
            executor.submit(run_league_calculation, league_id, args.season, args.start_round, args.target_round): league_id
            for league_id in league_ids
        }
        
        for future in as_completed(futures):
            league_id = futures[future]
            try:
                future.result()  # 等待任务完成，以便捕获异常
                logger.info(f"✅ 联赛ID {league_id} 的所有计算任务已成功完成。")
            except Exception as e:
                # 内部函数已经记录了详细错误，这里只记录一个概要
                logger.error(f"❌ 联赛ID {league_id} 的计算任务执行时发生顶层错误。")

    logger.info("所有指定联赛的计算任务均已执行完毕。")


if __name__ == "__main__":
    main()
