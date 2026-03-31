#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
优化的多轮次广义实力计算器
解决多线程并发和重复计算问题
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List, Tuple, Set
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger
from calculation.strength_repository import StrengthDataRepository
from calculation.strength_service import StrengthCalculationService
from calculation.multi_round_history_storage import MultiRoundHistoryStorageService

logger = get_logger(__name__)


class OptimizedMultiRoundCalculator:
    """
    优化的多轮次广义实力计算器
    特点:
    1. 真正的多线程并发处理 (轮次级别并发)
    2. 智能重复检查，避免重复计算
    3. 增量计算支持
    """

    def __init__(self, league_id: int, season: Optional[str] = None):
        """
        初始化计算器
        
        Args:
            league_id: 联赛ID
            season: 赛季
        """
        self.league_id = league_id
        self.season = season
        self.db = get_connection()
        self.repository = StrengthDataRepository(self.db)
        self.service = StrengthCalculationService()
        self.history_storage = MultiRoundHistoryStorageService(self.db)
        self.league_info = None
        self._lock = threading.Lock()
        
        logger.info(f"优化多轮次计算器初始化 - 联赛ID: {league_id}, 赛季: {season}")

    def calculate_multi_rounds_optimized(
        self, 
        start_round: int = 9,
        end_round: Optional[int] = None,
        max_workers: int = 6,
        force_recalculate: bool = False,
        skip_existing: bool = True
    ) -> Dict:
        """
        优化的多轮次计算 - 支持并发和增量计算
        
        Args:
            start_round: 起始轮次
            end_round: 结束轮次
            max_workers: 并发线程数
            force_recalculate: 是否强制重新计算已存在数据
            skip_existing: 是否跳过已存在的轮次
            
        Returns:
            计算结果统计
        """
        logger.info("=" * 80)
        logger.info("开始优化多轮次广义实力计算")
        logger.info(f"联赛ID: {self.league_id}, 赛季: {self.season}")
        logger.info(f"轮次范围: {start_round} - {end_round or '最新轮次'}")
        logger.info(f"并发数: {max_workers}, 跳过已存在: {skip_existing}")
        logger.info("=" * 80)

        start_time = time.time()

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
        rounds_to_calculate = [r for r in available_rounds if start_round <= r <= actual_end_round]
        
        # 4. 检查已存在的轮次数据（避免重复计算）
        if skip_existing and not force_recalculate:
            existing_rounds = self._get_existing_rounds()
            rounds_to_calculate = [r for r in rounds_to_calculate if r not in existing_rounds]
            if existing_rounds:
                logger.info(f"跳过已存在的 {len(existing_rounds)} 个轮次: {sorted(existing_rounds)}")
        
        if not rounds_to_calculate:
            logger.info("所有轮次已存在，无需计算")
            return {
                'success': True,
                'skipped': True,
                'total_rounds': 0,
                'rounds_calculated': [],
                'companies_processed': 0
            }

        logger.info(f"将并发计算 {len(rounds_to_calculate)} 个轮次: {rounds_to_calculate}")

        # 5. 并发计算多轮次 (这是关键优化点)
        results = {
            'success': True,
            'league_id': self.league_id,
            'season': self.season,
            'rounds_calculated': [],
            'rounds_failed': [],
            'total_rounds': len(rounds_to_calculate),
            'companies_processed': 0,
            'processing_time': 0
        }

        # 使用ThreadPoolExecutor实现真正的轮次级并发
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 提交所有轮次任务
            future_to_round = {
                executor.submit(self._calculate_single_round_optimized, round_num, start_round): round_num
                for round_num in rounds_to_calculate
            }

            # 收集结果
            for future in as_completed(future_to_round):
                round_num = future_to_round[future]
                try:
                    round_result = future.result()
                    if round_result['success']:
                        with self._lock:
                            results['rounds_calculated'].append(round_num)
                            results['companies_processed'] += round_result.get('companies_count', 0)
                        logger.info(f"✅ 第{round_num}轮计算完成: {round_result.get('companies_count', 0)} 家公司")
                    else:
                        results['rounds_failed'].append(round_num)
                        logger.error(f"❌ 第{round_num}轮计算失败: {round_result.get('error', 'Unknown')}")
                except Exception as e:
                    logger.error(f"❌ 第{round_num}轮计算异常: {e}")
                    results['rounds_failed'].append(round_num)

        # 6. 计算总时间并输出统计
        results['processing_time'] = time.time() - start_time
        
        logger.info("=" * 80)
        logger.info("优化多轮次计算完成统计:")
        logger.info(f"成功计算轮次: {len(results['rounds_calculated'])}/{results['total_rounds']}")
        logger.info(f"失败轮次: {len(results['rounds_failed'])}")
        logger.info(f"处理公司总数: {results['companies_processed']}")
        logger.info(f"处理时间: {results['processing_time']:.2f} 秒")
        if results['rounds_failed']:
            logger.warning(f"失败轮次详情: {results['rounds_failed']}")
        logger.info("=" * 80)

        return results

    def _get_existing_rounds(self) -> Set[int]:
        """检查已存在的计算结果"""
        try:
            query = """
            SELECT DISTINCT round_number
            FROM team_power_ratings
            WHERE league_id = %s 
            AND (season = %s OR %s IS NULL)
            """
            
            existing_data = self.db.execute_query(
                query, 
                (self.league_id, self.season, self.season), 
                fetch='all'
            )
            
            existing_rounds = {row['round_number'] for row in existing_data} if existing_data else set()
            
            if existing_rounds:
                logger.info(f"联赛ID {self.league_id} 已存在 {len(existing_rounds)} 个轮次的计算结果")
            
            return existing_rounds
            
        except Exception as e:
            logger.warning(f"检查已存在轮次时出错: {e}")
            return set()

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
            
            rounds_data = self.db.execute_query(query, (self.league_id, self.season, self.season), fetch='all')
            rounds = [row['round_number'] for row in rounds_data] if rounds_data else []
            
            logger.info(f"联赛ID {self.league_id} 找到 {len(rounds)} 个可用轮次")
            return rounds
            
        except Exception as e:
            logger.error(f"获取可用轮次时出错: {e}")
            return []

    def _calculate_single_round_optimized(self, target_round: int, start_round: int = 1) -> Dict:
        """
        优化的单轮次计算 - 每个轮次独立并发处理
        
        Args:
            target_round: 目标轮次
            start_round: 起始轮次
            
        Returns:
            该轮次的计算结果
        """
        # 为并发创建独立的数据库连接
        round_db = get_connection()
        round_repository = StrengthDataRepository(round_db)
        round_storage = MultiRoundHistoryStorageService(round_db)
        
        try:
            logger.debug(f"开始计算第{target_round}轮（线程独立）")
            
            # 加载该轮次的所有公司数据（使用累积数据）
            companies_data_map = round_repository.load_all_companies_data(
                league_id=self.league_id,
                season=self.season
            )
            
            # 过滤到目标轮次
            if companies_data_map:
                filtered_companies_data = {}
                for company_id, company_df in companies_data_map.items():
                    filtered_df = company_df[company_df['round_number'] <= target_round].copy()
                    if not filtered_df.empty:
                        filtered_companies_data[company_id] = filtered_df
                companies_data_map = filtered_companies_data
            
            if not companies_data_map:
                logger.warning(f"第{target_round}轮没有找到任何符合条件的公司数据")
                return {'success': False, 'error': f'No companies data for round {target_round}'}

            # 并行计算各公司的广义实力
            successful_companies = 0
            failed_companies = 0
            
            # 使用较小的线程池避免过度并发
            with ThreadPoolExecutor(max_workers=4) as company_executor:
                company_futures = {
                    company_executor.submit(
                        self._calculate_company_for_round_optimized, 
                        company_id, 
                        company_df, 
                        target_round,
                        start_round,
                        round_storage
                    ): company_id
                    for company_id, company_df in companies_data_map.items()
                }

                for future in as_completed(company_futures):
                    company_id = company_futures[future]
                    try:
                        future.result()
                        successful_companies += 1
                    except Exception as e:
                        failed_companies += 1
                        logger.error(f"第{target_round}轮公司{company_id}计算失败: {e}")

            return {
                'success': True,
                'round_number': target_round,
                'companies_count': successful_companies,
                'failed_count': failed_companies
            }
            
        except Exception as e:
            logger.error(f"第{target_round}轮整体计算失败: {e}")
            return {'success': False, 'error': str(e)}
        finally:
            # 关闭独立的数据库连接
            if 'round_db' in locals():
                round_db.close()

    def _calculate_company_for_round_optimized(
        self, 
        company_id: int, 
        matches_df: pd.DataFrame, 
        target_round: int,
        start_round: int,
        storage_service: MultiRoundHistoryStorageService
    ):
        """
        优化的公司轮次计算 - 使用独立连接和存储服务
        """
        company_name = matches_df['company_name'].iloc[0] if not matches_df.empty else f"Company_{company_id}"
        
        # 1. 计算广义实力
        team_powers = self.service.calculate_all_teams_strength(matches_df)
        if not team_powers:
            raise ValueError(f"公司{company_id}未能计算出实力结果")

        # 2. 存储到历史表（使用传入的独立存储服务）
        storage_service.save_round_history(
            team_powers=team_powers,
            league_info=self.league_info,
            company_id=company_id,
            company_name=company_name,
            season=self.season,
            round_number=target_round,
            matches_df=matches_df,
            start_round=start_round
        )

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

    def cleanup_rounds(self, rounds: List[int]) -> int:
        """
        清理指定轮次的数据（用于重新计算）
        
        Args:
            rounds: 要清理的轮次列表
            
        Returns:
            清理的记录总数
        """
        total_deleted = 0
        
        for round_num in rounds:
            try:
                deleted_count = self.history_storage.delete_round_data(
                    league_id=self.league_id,
                    season=self.season,
                    round_number=round_num
                )
                total_deleted += deleted_count
                logger.info(f"已清理第{round_num}轮数据: {deleted_count} 条记录")
            except Exception as e:
                logger.error(f"清理第{round_num}轮数据失败: {e}")
        
        logger.info(f"总计清理 {total_deleted} 条记录")
        return total_deleted


def run_optimized_calculation(
    league_id: int,
    season: Optional[str] = None,
    start_round: int = 9,
    end_round: Optional[int] = None,
    max_workers: int = 6,
    skip_existing: bool = True
) -> Dict:
    """
    运行优化计算的便捷函数
    
    Args:
        league_id: 联赛ID
        season: 赛季
        start_round: 起始轮次
        end_round: 结束轮次
        max_workers: 并发线程数
        skip_existing: 是否跳过已存在的轮次
        
    Returns:
        计算结果
    """
    calculator = OptimizedMultiRoundCalculator(league_id=league_id, season=season)
    return calculator.calculate_multi_rounds_optimized(
        start_round=start_round,
        end_round=end_round,
        max_workers=max_workers,
        skip_existing=skip_existing
    )


def run_all_leagues_optimized(
    season: Optional[str] = None,
    start_round: int = 9,
    end_round: Optional[int] = None,
    max_workers: int = 6,
    league_max_workers: int = 3,
    skip_existing: bool = True
) -> Dict:
    """
    优化的全联赛计算
    
    Args:
        season: 赛季
        start_round: 起始轮次
        end_round: 结束轮次
        max_workers: 每联赛内并发数
        league_max_workers: 联赛级别并发数
        skip_existing: 是否跳过已存在轮次
        
    Returns:
        所有联赛计算结果
    """
    from calculation.multi_round_strength_calculator import MultiRoundStrengthCalculator
    
    logger.info("=" * 100)
    logger.info("开始优化全联赛广义实力计算")
    logger.info("=" * 100)
    
    # 获取所有有赔率数据的联赛
    leagues = MultiRoundStrengthCalculator.get_leagues_with_odds_data(season=season)
    
    if not leagues:
        logger.error("未找到任何符合条件的联赛")
        return {'success': False, 'error': 'No leagues found'}
    
    logger.info(f"即将优化计算 {len(leagues)} 个联赛")
    
    all_results = {
        'success': True,
        'total_leagues': len(leagues),
        'leagues_completed': [],
        'leagues_failed': [],
        'total_processing_time': 0
    }
    
    start_time = time.time()
    
    # 联赛级别并发处理
    with ThreadPoolExecutor(max_workers=league_max_workers) as executor:
        futures = {}
        
        for league in leagues:
            league_id = league['league_id']
            league_name = league['name_cn']
            
            future = executor.submit(
                run_optimized_calculation,
                league_id, season, start_round, end_round, max_workers, skip_existing
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
                        'rounds_calculated': len(result.get('rounds_calculated', [])),
                        'companies_processed': result.get('companies_processed', 0),
                        'processing_time': result.get('processing_time', 0),
                        'skipped': result.get('skipped', False)
                    })
                    logger.info(f"✅ 联赛 {league_name} (ID:{league_id}) 优化计算完成")
                else:
                    all_results['leagues_failed'].append({
                        'league_id': league_id,
                        'league_name': league_name,
                        'error': result.get('error', 'Unknown')
                    })
                    logger.error(f"❌ 联赛 {league_name} (ID:{league_id}) 计算失败")
            except Exception as e:
                all_results['leagues_failed'].append({
                    'league_id': league_id,
                    'league_name': league_name,
                    'error': str(e)
                })
                logger.error(f"❌ 联赛 {league_name} (ID:{league_id}) 计算异常: {e}")
    
    # 统计结果
    all_results['total_processing_time'] = time.time() - start_time
    
    logger.info("=" * 100)
    logger.info("优化全联赛计算完成总结:")
    logger.info(f"成功联赛: {len(all_results['leagues_completed'])}/{all_results['total_leagues']}")
    logger.info(f"失败联赛: {len(all_results['leagues_failed'])}")
    logger.info(f"总处理时间: {all_results['total_processing_time']:.2f} 秒")
    logger.info("=" * 100)
    
    return all_results


def main():
    """命令行入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="优化多轮次广义实力计算器")
    parser.add_argument('--league-ids', type=str, help='联赛ID列表，逗号分隔')
    parser.add_argument('--season', type=str, help='赛季')
    parser.add_argument('--start-round', type=int, default=9, help='起始轮次')
    parser.add_argument('--end-round', type=int, help='结束轮次')
    parser.add_argument('--max-workers', type=int, default=6, help='并行线程数')
    parser.add_argument('--all-leagues', action='store_true', help='计算所有联赛')
    parser.add_argument('--league-max-workers', type=int, default=3, help='联赛级别并行数')
    parser.add_argument('--force-recalculate', action='store_true', help='强制重新计算')
    
    args = parser.parse_args()
    
    skip_existing = not args.force_recalculate
    
    # 全联赛计算模式
    if args.all_leagues:
        logger.info("启动优化全联赛计算模式")
        result = run_all_leagues_optimized(
            season=args.season,
            start_round=args.start_round,
            end_round=args.end_round,
            max_workers=args.max_workers,
            league_max_workers=args.league_max_workers,
            skip_existing=skip_existing
        )
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
    
    # 并行处理多个联赛
    with ThreadPoolExecutor(max_workers=min(3, len(league_ids))) as executor:
        futures = {}
        
        for league_id in league_ids:
            future = executor.submit(
                run_optimized_calculation,
                league_id, args.season, args.start_round, args.end_round, 
                args.max_workers, skip_existing
            )
            futures[future] = league_id
        
        # 收集结果
        for future in as_completed(futures):
            league_id = futures[future]
            try:
                result = future.result()
                if result['success']:
                    logger.info(f"✅ 联赛ID {league_id} 优化计算完成")
                else:
                    logger.error(f"❌ 联赛ID {league_id} 计算失败: {result.get('error')}")
            except Exception as e:
                logger.error(f"❌ 联赛ID {league_id} 计算异常: {e}")


if __name__ == "__main__":
    main()