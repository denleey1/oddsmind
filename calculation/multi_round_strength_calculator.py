#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
多轮次广义实力计算器 - 支持历史轮次的广义实力计算和存储
基于现有的MySQLGeneralStrengthCalculator，增加多轮次历史计算功能
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger
from calculation.strength_repository import StrengthDataRepository
from calculation.mysql_general_strength_calculator import MySQLGeneralStrengthCalculator
from calculation.multi_round_history_storage import MultiRoundHistoryStorageService

logger = get_logger(__name__)


class MultiRoundStrengthCalculator:
    """
    多轮次广义实力计算器
    支持从指定轮次开始，逐轮计算并存储广义实力历史数据
    """

    def __init__(self, league_id: int, season: Optional[str] = None):
        """
        初始化计算器
        
        Args:
            league_id: 联赛ID
            season: 赛季 (如 "2024-25")
        """
        self.league_id = league_id
        self.season = season
        self.db = get_connection()
        self.repository = StrengthDataRepository(self.db)
        # 注意：MySQLGeneralStrengthCalculator 需要在使用时初始化，因为它需要具体的参数
        self.history_storage = MultiRoundHistoryStorageService(self.db)
        self.league_info = None
        self._print_lock = threading.Lock()
        
        logger.info(f"多轮次广义实力计算器已初始化 - 联赛ID: {league_id}, 赛季: {season}")

    def calculate_multi_rounds(
        self, 
        start_round: int = 9,
        end_round: Optional[int] = None,
        max_workers: int = 8
    ) -> Dict:
        """
        计算从起始轮次到结束轮次的所有轮次广义实力
        
        Args:
            start_round: 起始轮次（默认第9轮）
            end_round: 结束轮次（None表示到当前最新轮次）
            max_workers: 并行线程数
            
        Returns:
            计算结果统计信息
        """
        logger.info("=" * 80)
        logger.info(f"开始多轮次广义实力计算")
        logger.info(f"联赛ID: {self.league_id}, 赛季: {self.season}")
        logger.info(f"轮次范围: {start_round} - {end_round if end_round else '最新轮次'}")
        logger.info("=" * 80)

        # 1. 加载联赛信息
        self.league_info = self.repository.get_league_info(self.league_id)
        if not self.league_info:
            logger.error(f"联赛ID {self.league_id} 信息未找到")
            return {'success': False, 'error': 'League not found'}

        # 2. 获取可用轮次范围
        available_rounds = self._get_available_rounds()
        if not available_rounds:
            logger.error("未找到任何可用轮次数据")
            return {'success': False, 'error': 'No rounds available'}
        
        # 3. 确定计算轮次范围
        max_available_round = max(available_rounds)
        actual_end_round = min(end_round or max_available_round, max_available_round)
        
        if start_round > actual_end_round:
            logger.error(f"起始轮次 {start_round} 大于结束轮次 {actual_end_round}")
            return {'success': False, 'error': 'Invalid round range'}
        
        rounds_to_calculate = [r for r in available_rounds if start_round <= r <= actual_end_round]
        logger.info(f"将计算 {len(rounds_to_calculate)} 个轮次: {rounds_to_calculate}")

        # 4. 逐轮计算广义实力
        results = {
            'success': True,
            'league_id': self.league_id,
            'season': self.season,
            'rounds_calculated': [],
            'rounds_failed': [],
            'total_rounds': len(rounds_to_calculate),
            'companies_processed': 0
        }

        for round_num in rounds_to_calculate:
            try:
                round_result = self._calculate_single_round(round_num, max_workers, start_round)
                if round_result['success']:
                    results['rounds_calculated'].append(round_num)
                    results['companies_processed'] += round_result.get('companies_count', 0)
                else:
                    results['rounds_failed'].append(round_num)
                    logger.error(f"第{round_num}轮计算失败: {round_result.get('error', 'Unknown error')}")
            except Exception as e:
                logger.error(f"第{round_num}轮计算出现异常: {e}", exc_info=True)
                results['rounds_failed'].append(round_num)

        # 5. 输出结果统计
        logger.info("=" * 80)
        logger.info("多轮次计算完成统计:")
        logger.info(f"成功计算轮次: {len(results['rounds_calculated'])}/{results['total_rounds']}")
        logger.info(f"失败轮次: {len(results['rounds_failed'])}")
        logger.info(f"处理公司总数: {results['companies_processed']}")
        if results['rounds_failed']:
            logger.warning(f"失败轮次详情: {results['rounds_failed']}")
        logger.info("=" * 80)

        return results

    def _get_available_rounds(self) -> List[int]:
        """获取当前联赛可用的轮次列表"""
        try:
            query = """
            SELECT DISTINCT round_number 
            FROM matches 
            WHERE league_id = %s 
            AND (season = %s OR %s IS NULL)
            AND round_number IS NOT NULL 
            AND round_number > 0
            ORDER BY round_number
            """
            
            # 使用数据库连接对象的execute_query方法
            rounds_data = self.db.execute_query(query, (self.league_id, self.season, self.season), fetch='all')
            rounds = [row['round_number'] for row in rounds_data] if rounds_data else []
            
            logger.info(f"联赛ID {self.league_id} 找到 {len(rounds)} 个可用轮次: {rounds}")
            return rounds
            
        except Exception as e:
            logger.error(f"获取可用轮次时出错: {e}")
            return []

    @staticmethod
    def get_leagues_with_odds_data(db_connection=None, season: Optional[str] = None, min_rounds: int = 9) -> List[Dict]:
        """
        获取所有有赔率数据的联赛列表
        
        Args:
            db_connection: 数据库连接
            season: 赛季过滤
            min_rounds: 最小轮次数要求
            
        Returns:
            联赛信息列表，包含 league_id, name_cn, max_round, companies_count 等
        """
        db = db_connection or get_connection()
        
        try:
            query = """
            SELECT 
                m.league_id,
                l.name_cn,
                l.name_en,
                COUNT(DISTINCT m.round_number) as total_rounds,
                MAX(m.round_number) as max_round,
                COUNT(DISTINCT eo.company_id) as companies_count,
                COUNT(DISTINCT m.match_id) as total_matches
            FROM matches m
            JOIN leagues l ON m.league_id = l.league_id  
            JOIN european_odds eo ON m.match_id = eo.match_id
            WHERE m.round_number IS NOT NULL 
            AND m.round_number > 0
            AND eo.initial_home IS NOT NULL 
            AND eo.initial_draw IS NOT NULL 
            AND eo.initial_away IS NOT NULL
            AND (m.season = %s OR %s IS NULL)
            GROUP BY m.league_id, l.name_cn, l.name_en
            HAVING total_rounds >= %s
            ORDER BY companies_count DESC, total_rounds DESC
            """
            
            results = db.execute_query(query, (season, season, min_rounds), fetch='all')
            
            if results:
                logger.info(f"发现 {len(results)} 个联赛有足够的赔率数据 (最少{min_rounds}轮)")
                for league in results:
                    logger.info(f"  联赛ID {league['league_id']}: {league['name_cn']} "
                              f"({league['total_rounds']}轮, {league['companies_count']}家公司, "
                              f"{league['total_matches']}场比赛)")
            
            return results or []
            
        except Exception as e:
            logger.error(f"获取有赔率数据的联赛列表失败: {e}")
            return []

    def calculate_single_round(self, target_round: int, max_workers: int = 8, start_round: int = 1) -> Dict:
        """
        计算单个轮次的广义实力（公开方法）
        
        Args:
            target_round: 目标轮次
            max_workers: 并行线程数
            start_round: 起始轮次（默认1）
            
        Returns:
            计算结果
        """
        return self._calculate_single_round(target_round, max_workers, start_round)
    
    def _calculate_single_round(self, target_round: int, max_workers: int = 8, start_round: int = 1) -> Dict:
        """
        计算单个轮次的所有公司广义实力
        
        Args:
            target_round: 目标轮次
            max_workers: 并行线程数
            
        Returns:
            该轮次的计算结果
        """
        logger.info(f"--- 开始计算第{target_round}轮广义实力 ---")
        
        # 加载该轮次的所有公司数据（使用从第1轮到target_round的累积数据）
        companies_data_map = self.repository.load_all_companies_data(
            league_id=self.league_id,
            season=self.season
        )
        
        # 手动过滤到目标轮次（累积数据：第1轮到target_round）
        if companies_data_map:
            filtered_companies_data = {}
            for company_id, company_df in companies_data_map.items():
                # 过滤到目标轮次（包含target_round及之前的所有轮次）
                filtered_df = company_df[company_df['round_number'] <= target_round].copy()
                if not filtered_df.empty:
                    filtered_companies_data[company_id] = filtered_df
            companies_data_map = filtered_companies_data
        
        if not companies_data_map:
            logger.warning(f"第{target_round}轮没有找到任何符合条件的公司数据")
            return {'success': False, 'error': f'No companies data for round {target_round}'}

        logger.info(f"第{target_round}轮找到 {len(companies_data_map)} 家公司数据")
        
        # 并行计算各公司的广义实力
        successful_companies = 0
        failed_companies = 0
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    self._calculate_company_for_round, 
                    company_id, 
                    company_df, 
                    target_round,
                    start_round
                ): company_id
                for company_id, company_df in companies_data_map.items()
            }

            for future in as_completed(futures):
                company_id = futures[future]
                try:
                    future.result()
                    successful_companies += 1
                    logger.debug(f"✅ 第{target_round}轮 - 公司ID {company_id} 计算成功")
                except Exception as e:
                    failed_companies += 1
                    logger.error(f"❌ 第{target_round}轮 - 公司ID {company_id} 计算失败: {e}")

        logger.info(f"--- 第{target_round}轮计算完成: 成功 {successful_companies}, 失败 {failed_companies} ---")
        
        return {
            'success': True,
            'round_number': target_round,
            'companies_count': successful_companies,
            'failed_count': failed_companies
        }

    def _calculate_company_for_round(
        self, 
        company_id: int, 
        matches_df: pd.DataFrame, 
        target_round: int,
        start_round: int = 1
    ):
        """
        为特定轮次和公司计算广义实力并存储到历史表
        
        Args:
            company_id: 公司ID
            matches_df: 该公司的比赛数据（累积到target_round）
            target_round: 目标轮次
        """
        company_name = matches_df['company_name'].iloc[0] if not matches_df.empty else f"Company_{company_id}"
        
        # 1. 计算广义实力 - 使用正确的MySQLGeneralStrengthCalculator
        calculator = MySQLGeneralStrengthCalculator(
            league_id=self.league_id,
            season=self.season,
            target_round=target_round
        )
        
        # 为单个公司计算（模拟原有的_calculate_for_company方法）
        team_powers = calculator._calculate_for_company(company_id, matches_df)
        if not team_powers:
            raise ValueError(f"公司{company_id}未能计算出实力结果")

        # 2. 存储到历史表
        self.history_storage.save_round_history(
            team_powers=team_powers,
            league_info=self.league_info,
            company_id=company_id,
            company_name=company_name,
            season=self.season,
            round_number=target_round,
            matches_df=matches_df,
            start_round=start_round
        )

    def calculate_specific_rounds(
        self, 
        round_numbers: List[int], 
        max_workers: int = 8
    ) -> Dict:
        """
        计算指定的轮次列表
        
        Args:
            round_numbers: 要计算的轮次列表
            max_workers: 并行线程数
            
        Returns:
            计算结果统计
        """
        logger.info(f"开始计算指定轮次: {round_numbers}")
        
        available_rounds = self._get_available_rounds()
        valid_rounds = [r for r in round_numbers if r in available_rounds]
        invalid_rounds = [r for r in round_numbers if r not in available_rounds]
        
        if invalid_rounds:
            logger.warning(f"以下轮次数据不可用，将跳过: {invalid_rounds}")
        
        if not valid_rounds:
            return {'success': False, 'error': 'No valid rounds to calculate'}
        
        # 使用现有的多轮次计算逻辑
        results = {
            'success': True,
            'league_id': self.league_id,
            'season': self.season,
            'rounds_calculated': [],
            'rounds_failed': [],
            'rounds_skipped': invalid_rounds,
            'total_rounds': len(valid_rounds),
            'companies_processed': 0
        }

        for round_num in valid_rounds:
            try:
                # 对于指定轮次，start_round 应该是最小的轮次
                min_start_round = min(valid_rounds)
                round_result = self._calculate_single_round(round_num, max_workers, min_start_round)
                if round_result['success']:
                    results['rounds_calculated'].append(round_num)
                    results['companies_processed'] += round_result.get('companies_count', 0)
                else:
                    results['rounds_failed'].append(round_num)
            except Exception as e:
                logger.error(f"第{round_num}轮计算异常: {e}", exc_info=True)
                results['rounds_failed'].append(round_num)

        logger.info(f"指定轮次计算完成: 成功 {len(results['rounds_calculated'])}/{len(valid_rounds)}")
        return results

    def get_calculation_summary(self) -> Dict:
        """获取当前联赛的历史计算摘要信息"""
        try:
            summary = self.history_storage.get_league_calculation_summary(
                league_id=self.league_id,
                season=self.season
            )
            return summary
        except Exception as e:
            logger.error(f"获取计算摘要失败: {e}")
            return {}

    def cleanup_round_data(self, round_number: int, company_id: Optional[int] = None) -> bool:
        """
        清理指定轮次的历史数据（用于重新计算）
        
        Args:
            round_number: 轮次
            company_id: 公司ID（None表示清理该轮次所有公司数据）
            
        Returns:
            是否成功清理
        """
        try:
            deleted_count = self.history_storage.delete_round_data(
                league_id=self.league_id,
                season=self.season,
                round_number=round_number,
                company_id=company_id
            )
            
            logger.info(f"已清理第{round_number}轮数据: {deleted_count} 条记录")
            return True
            
        except Exception as e:
            logger.error(f"清理第{round_number}轮数据失败: {e}")
            return False


def run_multi_round_calculation(
    league_id: int,
    season: Optional[str] = None,
    start_round: int = 9,
    end_round: Optional[int] = None,
    max_workers: int = 8
) -> Dict:
    """
    运行多轮次计算的便捷函数
    
    Args:
        league_id: 联赛ID
        season: 赛季
        start_round: 起始轮次
        end_round: 结束轮次
        max_workers: 并行线程数
        
    Returns:
        计算结果
    """
    calculator = MultiRoundStrengthCalculator(league_id=league_id, season=season)
    return calculator.calculate_multi_rounds(
        start_round=start_round,
        end_round=end_round,
        max_workers=max_workers
    )


def run_all_leagues_calculation(
    season: Optional[str] = None,
    start_round: int = 9,
    end_round: Optional[int] = None,
    max_workers: int = 8,
    league_max_workers: int = 4,
    min_rounds: int = 9
) -> Dict:
    """
    计算所有有赔率数据的联赛
    
    Args:
        season: 赛季
        start_round: 起始轮次
        end_round: 结束轮次  
        max_workers: 每个联赛内的并行线程数
        league_max_workers: 联赛级别的并行数
        min_rounds: 联赛最小轮次要求
        
    Returns:
        所有联赛的计算结果
    """
    logger.info("=" * 100)
    logger.info("开始全联赛广义实力计算")
    logger.info("=" * 100)
    
    # 1. 获取所有有赔率数据的联赛
    leagues = MultiRoundStrengthCalculator.get_leagues_with_odds_data(
        season=season, 
        min_rounds=min_rounds
    )
    
    if not leagues:
        logger.error("未找到任何符合条件的联赛")
        return {'success': False, 'error': 'No leagues found'}
    
    logger.info(f"即将计算 {len(leagues)} 个联赛")
    
    # 2. 并行计算所有联赛
    all_results = {
        'success': True,
        'total_leagues': len(leagues),
        'leagues_completed': [],
        'leagues_failed': [],
        'total_rounds_calculated': 0,
        'total_companies_processed': 0
    }
    
    with ThreadPoolExecutor(max_workers=league_max_workers) as executor:
        futures = {}
        
        for league in leagues:
            league_id = league['league_id']
            league_name = league['name_cn']
            
            calculator = MultiRoundStrengthCalculator(league_id=league_id, season=season)
            future = executor.submit(
                calculator.calculate_multi_rounds,
                start_round, end_round, max_workers
            )
            futures[future] = {'league_id': league_id, 'league_name': league_name}
        
        # 收集结果
        for future in as_completed(futures):
            league_info = futures[future]
            league_id = league_info['league_id']
            league_name = league_info['league_name']
            
            try:
                result = future.result()
                if result['success']:
                    all_results['leagues_completed'].append({
                        'league_id': league_id,
                        'league_name': league_name,
                        'rounds_calculated': len(result['rounds_calculated']),
                        'companies_processed': result['companies_processed']
                    })
                    all_results['total_rounds_calculated'] += len(result['rounds_calculated'])
                    all_results['total_companies_processed'] += result['companies_processed']
                    logger.info(f"✅ 联赛 {league_name} (ID:{league_id}) 计算完成")
                else:
                    all_results['leagues_failed'].append({
                        'league_id': league_id,
                        'league_name': league_name,
                        'error': result.get('error', 'Unknown')
                    })
                    logger.error(f"❌ 联赛 {league_name} (ID:{league_id}) 计算失败: {result.get('error', 'Unknown')}")
            except Exception as e:
                all_results['leagues_failed'].append({
                    'league_id': league_id,
                    'league_name': league_name,
                    'error': str(e)
                })
                logger.error(f"❌ 联赛 {league_name} (ID:{league_id}) 计算异常: {e}")
    
    # 3. 输出总结
    logger.info("=" * 100)
    logger.info("全联赛广义实力计算完成总结:")
    logger.info(f"成功联赛: {len(all_results['leagues_completed'])}/{all_results['total_leagues']}")
    logger.info(f"失败联赛: {len(all_results['leagues_failed'])}")
    logger.info(f"总计算轮次: {all_results['total_rounds_calculated']}")
    logger.info(f"总处理公司数: {all_results['total_companies_processed']}")
    
    if all_results['leagues_completed']:
        logger.info("\n成功联赛详情:")
        for league in all_results['leagues_completed']:
            logger.info(f"  {league['league_name']} (ID:{league['league_id']}): "
                       f"{league['rounds_calculated']}轮, {league['companies_processed']}家公司")
    
    if all_results['leagues_failed']:
        logger.warning(f"\n失败联赛详情:")
        for league in all_results['leagues_failed']:
            logger.warning(f"  {league['league_name']} (ID:{league['league_id']}): {league['error']}")
    
    logger.info("=" * 100)
    
    return all_results


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="多轮次广义实力计算器")
    parser.add_argument('--league-ids', type=str, 
                       help='联赛ID列表，逗号分隔 (例如: 25,15,284)')
    parser.add_argument('--season', type=str, help='赛季 (如 2024-25)')
    parser.add_argument('--start-round', type=int, default=9, 
                       help='起始轮次 (默认: 9)')
    parser.add_argument('--end-round', type=int, help='结束轮次 (默认: 最新轮次)')
    parser.add_argument('--max-workers', type=int, default=8,
                       help='并行线程数 (默认: 8)')
    parser.add_argument('--specific-rounds', type=str,
                       help='指定轮次列表，逗号分隔 (例如: 10,15,20)')
    parser.add_argument('--all-leagues', action='store_true',
                       help='计算所有有赔率数据的联赛')
    parser.add_argument('--league-max-workers', type=int, default=4,
                       help='全联赛模式下联赛级别并行数 (默认: 4)')
    parser.add_argument('--min-rounds', type=int, default=9,
                       help='全联赛模式下联赛最小轮次要求 (默认: 9)')
    
    args = parser.parse_args()
    
    # 全联赛计算模式
    if args.all_leagues:
        logger.info("启动全联赛计算模式")
        result = run_all_leagues_calculation(
            season=args.season,
            start_round=args.start_round,
            end_round=args.end_round,
            max_workers=args.max_workers,
            league_max_workers=args.league_max_workers,
            min_rounds=args.min_rounds
        )
        
        if result['success']:
            logger.info("✅ 全联赛计算成功完成")
        else:
            logger.error("❌ 全联赛计算失败")
        return
    
    # 指定联赛计算模式
    if not args.league_ids:
        logger.error("必须指定 --league-ids 或使用 --all-leagues 参数")
        return
    
    try:
        league_ids = [int(lid.strip()) for lid in args.league_ids.split(',')]
    except ValueError:
        logger.error("无法解析联赛ID参数")
        return
    
    specific_rounds = None
    if args.specific_rounds:
        try:
            specific_rounds = [int(r.strip()) for r in args.specific_rounds.split(',')]
        except ValueError:
            logger.error("无法解析指定轮次参数")
            return
    
    # 并行处理多个联赛
    with ThreadPoolExecutor(max_workers=min(4, len(league_ids))) as executor:
        futures = {}
        
        for league_id in league_ids:
            calculator = MultiRoundStrengthCalculator(league_id=league_id, season=args.season)
            
            if specific_rounds:
                future = executor.submit(
                    calculator.calculate_specific_rounds,
                    specific_rounds, args.max_workers
                )
            else:
                future = executor.submit(
                    calculator.calculate_multi_rounds,
                    args.start_round, args.end_round, args.max_workers
                )
            
            futures[future] = league_id
        
        # 收集结果
        for future in as_completed(futures):
            league_id = futures[future]
            try:
                result = future.result()
                if result['success']:
                    logger.info(f"✅ 联赛ID {league_id} 计算完成")
                else:
                    logger.error(f"❌ 联赛ID {league_id} 计算失败: {result.get('error', 'Unknown')}")
            except Exception as e:
                logger.error(f"❌ 联赛ID {league_id} 计算异常: {e}")
    
    logger.info("所有联赛的多轮次计算任务已完成")


if __name__ == "__main__":
    main()