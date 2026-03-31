#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
批量多轮次广义实力处理器
支持批量处理36个联赛的多轮次广义实力计算
"""
import sys
from pathlib import Path
from typing import Optional, Dict, List, Any
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from dataclasses import dataclass, field

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from core.logger import get_logger
from calculation.multi_round_strength_calculator import MultiRoundStrengthCalculator
from calculation.multi_round_history_storage import MultiRoundHistoryStorageService
from database.connection import get_connection

logger = get_logger(__name__)


@dataclass
class BatchProcessingConfig:
    """批量处理配置"""
    league_ids: List[int] = field(default_factory=list)
    season: Optional[str] = None
    start_round: int = 9
    end_round: Optional[int] = None
    specific_rounds: Optional[List[int]] = None
    max_league_workers: int = 4  # 联赛级别并行数
    max_company_workers: int = 8  # 公司级别并行数
    progress_report_interval: int = 30  # 进度报告间隔（秒）
    retry_failed: bool = True  # 是否重试失败的任务
    max_retries: int = 2  # 最大重试次数


@dataclass
class ProcessingResult:
    """处理结果统计"""
    total_leagues: int = 0
    successful_leagues: int = 0
    failed_leagues: int = 0
    total_rounds: int = 0
    successful_rounds: int = 0
    failed_rounds: int = 0
    total_companies: int = 0
    processing_time_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)
    league_results: Dict[int, Dict] = field(default_factory=dict)


class BatchMultiRoundProcessor:
    """批量多轮次处理器"""

    def __init__(self, config: BatchProcessingConfig):
        """
        初始化批量处理器
        
        Args:
            config: 批量处理配置
        """
        self.config = config
        self.db = get_connection()
        self.storage_service = MultiRoundHistoryStorageService(self.db)
        self._progress_lock = threading.Lock()
        self._progress_data = {
            'completed_leagues': 0,
            'total_leagues': len(config.league_ids),
            'current_operations': {},
            'start_time': None
        }
        
        logger.info(f"批量多轮次处理器已初始化，将处理 {len(config.league_ids)} 个联赛")

    def process_all_leagues(self) -> ProcessingResult:
        """
        处理所有配置的联赛
        
        Returns:
            处理结果统计
        """
        start_time = time.time()
        self._progress_data['start_time'] = start_time
        
        result = ProcessingResult(
            total_leagues=len(self.config.league_ids)
        )

        logger.info("=" * 100)
        logger.info("开始批量多轮次广义实力计算")
        logger.info(f"联赛数量: {len(self.config.league_ids)}")
        logger.info(f"联赛列表: {self.config.league_ids}")
        logger.info(f"赛季: {self.config.season or '所有赛季'}")
        logger.info(f"轮次范围: {self.config.start_round} - {self.config.end_round or '最新'}")
        if self.config.specific_rounds:
            logger.info(f"指定轮次: {self.config.specific_rounds}")
        logger.info(f"联赛并发数: {self.config.max_league_workers}")
        logger.info(f"公司并发数: {self.config.max_company_workers}")
        logger.info("=" * 100)

        # 启动进度报告线程
        progress_thread = threading.Thread(target=self._progress_reporter, daemon=True)
        progress_thread.start()

        # 使用线程池并行处理联赛
        with ThreadPoolExecutor(max_workers=self.config.max_league_workers) as executor:
            # 提交所有任务
            future_to_league = {}
            for league_id in self.config.league_ids:
                future = executor.submit(self._process_single_league, league_id)
                future_to_league[future] = league_id

            # 收集结果
            for future in as_completed(future_to_league):
                league_id = future_to_league[future]
                
                try:
                    league_result = future.result()
                    result.league_results[league_id] = league_result
                    
                    if league_result['success']:
                        result.successful_leagues += 1
                        result.total_rounds += league_result.get('total_rounds', 0)
                        result.successful_rounds += len(league_result.get('rounds_calculated', []))
                        result.failed_rounds += len(league_result.get('rounds_failed', []))
                        result.total_companies += league_result.get('companies_processed', 0)
                        
                        logger.info(f"✅ 联赛 {league_id} 处理成功: "
                                  f"{len(league_result.get('rounds_calculated', []))} 轮成功, "
                                  f"{len(league_result.get('rounds_failed', []))} 轮失败")
                    else:
                        result.failed_leagues += 1
                        error_msg = f"联赛 {league_id} 处理失败: {league_result.get('error', 'Unknown error')}"
                        result.errors.append(error_msg)
                        logger.error(f"❌ {error_msg}")
                        
                except Exception as e:
                    result.failed_leagues += 1
                    error_msg = f"联赛 {league_id} 处理异常: {str(e)}"
                    result.errors.append(error_msg)
                    logger.error(f"❌ {error_msg}", exc_info=True)
                
                # 更新进度
                with self._progress_lock:
                    self._progress_data['completed_leagues'] += 1

        # 处理失败重试
        if self.config.retry_failed and result.failed_leagues > 0:
            logger.info(f"开始重试 {result.failed_leagues} 个失败的联赛")
            self._retry_failed_leagues(result)

        # 计算总处理时间
        result.processing_time_seconds = time.time() - start_time

        # 输出最终统计
        self._print_final_summary(result)

        return result

    def _process_single_league(self, league_id: int) -> Dict:
        """
        处理单个联赛
        
        Args:
            league_id: 联赛ID
            
        Returns:
            处理结果
        """
        # 更新当前操作状态
        with self._progress_lock:
            self._progress_data['current_operations'][league_id] = f"开始处理联赛 {league_id}"

        try:
            calculator = MultiRoundStrengthCalculator(
                league_id=league_id,
                season=self.config.season
            )

            # 根据配置选择计算方式
            if self.config.specific_rounds:
                with self._progress_lock:
                    self._progress_data['current_operations'][league_id] = f"计算联赛 {league_id} 指定轮次"
                
                result = calculator.calculate_specific_rounds(
                    round_numbers=self.config.specific_rounds,
                    max_workers=self.config.max_company_workers
                )
            else:
                with self._progress_lock:
                    self._progress_data['current_operations'][league_id] = f"计算联赛 {league_id} 多轮次"
                
                result = calculator.calculate_multi_rounds(
                    start_round=self.config.start_round,
                    end_round=self.config.end_round,
                    max_workers=self.config.max_company_workers
                )

            # 清除操作状态
            with self._progress_lock:
                self._progress_data['current_operations'].pop(league_id, None)

            return result

        except Exception as e:
            with self._progress_lock:
                self._progress_data['current_operations'].pop(league_id, None)
            
            logger.error(f"联赛 {league_id} 处理异常: {e}", exc_info=True)
            return {
                'success': False,
                'league_id': league_id,
                'error': str(e),
                'total_rounds': 0,
                'rounds_calculated': [],
                'rounds_failed': [],
                'companies_processed': 0
            }

    def _retry_failed_leagues(self, result: ProcessingResult):
        """重试失败的联赛"""
        failed_league_ids = [
            league_id for league_id, league_result in result.league_results.items()
            if not league_result['success']
        ]
        
        for retry_attempt in range(self.config.max_retries):
            if not failed_league_ids:
                break
                
            logger.info(f"第 {retry_attempt + 1} 次重试，处理 {len(failed_league_ids)} 个失败联赛")
            
            retry_results = []
            with ThreadPoolExecutor(max_workers=min(2, len(failed_league_ids))) as executor:
                future_to_league = {
                    executor.submit(self._process_single_league, league_id): league_id
                    for league_id in failed_league_ids
                }
                
                for future in as_completed(future_to_league):
                    league_id = future_to_league[future]
                    try:
                        league_result = future.result()
                        result.league_results[league_id] = league_result
                        
                        if league_result['success']:
                            retry_results.append((league_id, True))
                            # 更新统计
                            result.successful_leagues += 1
                            result.failed_leagues -= 1
                        else:
                            retry_results.append((league_id, False))
                            
                    except Exception as e:
                        logger.error(f"重试联赛 {league_id} 异常: {e}")
                        retry_results.append((league_id, False))
            
            # 更新失败列表
            failed_league_ids = [league_id for league_id, success in retry_results if not success]
            
            if failed_league_ids:
                logger.warning(f"重试后仍失败的联赛: {failed_league_ids}")
            else:
                logger.info("所有联赛重试成功")
                break

    def _progress_reporter(self):
        """进度报告线程"""
        while True:
            time.sleep(self.config.progress_report_interval)
            
            with self._progress_lock:
                completed = self._progress_data['completed_leagues']
                total = self._progress_data['total_leagues']
                start_time = self._progress_data['start_time']
                current_ops = dict(self._progress_data['current_operations'])
            
            if completed >= total:
                break
            
            # 计算进度和预估时间
            progress_percent = (completed / total) * 100 if total > 0 else 0
            elapsed_time = time.time() - start_time if start_time else 0
            
            if completed > 0:
                avg_time_per_league = elapsed_time / completed
                remaining_time = avg_time_per_league * (total - completed)
                eta_minutes = remaining_time / 60
            else:
                eta_minutes = 0
            
            logger.info(f"📊 进度报告: {completed}/{total} 联赛已完成 "
                       f"({progress_percent:.1f}%), "
                       f"预计剩余时间: {eta_minutes:.1f} 分钟")
            
            # 显示当前正在处理的操作
            if current_ops:
                logger.info(f"正在进行的操作: {list(current_ops.values())}")

    def _print_final_summary(self, result: ProcessingResult):
        """打印最终统计摘要"""
        logger.info("=" * 100)
        logger.info("批量多轮次计算完成统计:")
        logger.info("-" * 50)
        logger.info(f"联赛处理: {result.successful_leagues}/{result.total_leagues} 成功")
        logger.info(f"轮次处理: {result.successful_rounds}/{result.total_rounds} 成功")
        logger.info(f"公司数据: {result.total_companies} 个")
        logger.info(f"处理时间: {result.processing_time_seconds:.2f} 秒 ({result.processing_time_seconds/60:.2f} 分钟)")
        
        if result.failed_leagues > 0:
            logger.warning(f"失败联赛数: {result.failed_leagues}")
            logger.warning("失败详情:")
            for i, error in enumerate(result.errors, 1):
                logger.warning(f"  {i}. {error}")
        
        # 成功率统计
        league_success_rate = (result.successful_leagues / result.total_leagues) * 100 if result.total_leagues > 0 else 0
        round_success_rate = (result.successful_rounds / result.total_rounds) * 100 if result.total_rounds > 0 else 0
        
        logger.info(f"成功率: 联赛 {league_success_rate:.1f}%, 轮次 {round_success_rate:.1f}%")
        logger.info("=" * 100)

    def get_processing_status(self) -> Dict:
        """获取当前处理状态"""
        with self._progress_lock:
            return dict(self._progress_data)

    def cleanup_and_retry_league(self, league_id: int, rounds: Optional[List[int]] = None) -> Dict:
        """
        清理并重新计算指定联赛
        
        Args:
            league_id: 联赛ID
            rounds: 要清理的轮次列表（None表示所有轮次）
            
        Returns:
            重计算结果
        """
        logger.info(f"开始清理并重新计算联赛 {league_id}")
        
        try:
            # 清理历史数据
            if rounds:
                for round_num in rounds:
                    self.storage_service.delete_round_data(
                        league_id=league_id,
                        season=self.config.season,
                        round_number=round_num
                    )
            else:
                # 清理所有轮次数据（通过删除所有记录）
                # 这里需要实现一个删除联赛所有历史数据的方法
                pass
            
            # 重新计算
            calculator = MultiRoundStrengthCalculator(
                league_id=league_id,
                season=self.config.season
            )
            
            if rounds:
                result = calculator.calculate_specific_rounds(
                    round_numbers=rounds,
                    max_workers=self.config.max_company_workers
                )
            else:
                result = calculator.calculate_multi_rounds(
                    start_round=self.config.start_round,
                    end_round=self.config.end_round,
                    max_workers=self.config.max_company_workers
                )
            
            logger.info(f"联赛 {league_id} 清理重算完成")
            return result
            
        except Exception as e:
            logger.error(f"联赛 {league_id} 清理重算失败: {e}")
            return {'success': False, 'error': str(e)}


# 便捷函数
def create_batch_config(
    league_ids: List[int],
    season: Optional[str] = None,
    start_round: int = 9,
    end_round: Optional[int] = None,
    specific_rounds: Optional[List[int]] = None,
    max_league_workers: int = 4,
    max_company_workers: int = 8
) -> BatchProcessingConfig:
    """
    创建批量处理配置的便捷函数
    
    Args:
        league_ids: 联赛ID列表
        season: 赛季
        start_round: 起始轮次
        end_round: 结束轮次
        specific_rounds: 指定轮次列表
        max_league_workers: 联赛并发数
        max_company_workers: 公司并发数
        
    Returns:
        批量处理配置
    """
    return BatchProcessingConfig(
        league_ids=league_ids,
        season=season,
        start_round=start_round,
        end_round=end_round,
        specific_rounds=specific_rounds,
        max_league_workers=max_league_workers,
        max_company_workers=max_company_workers
    )


def run_batch_processing(config: BatchProcessingConfig) -> ProcessingResult:
    """
    运行批量处理的便捷函数
    
    Args:
        config: 批量处理配置
        
    Returns:
        处理结果
    """
    processor = BatchMultiRoundProcessor(config)
    return processor.process_all_leagues()


def main():
    """命令行入口"""
    import argparse
    import json
    
    parser = argparse.ArgumentParser(description="批量多轮次广义实力处理器")
    parser.add_argument('--config', type=str, help='配置文件路径 (JSON格式)')
    parser.add_argument('--league-ids', type=str, help='联赛ID列表，逗号分隔')
    parser.add_argument('--season', type=str, help='赛季')
    parser.add_argument('--start-round', type=int, default=9, help='起始轮次')
    parser.add_argument('--end-round', type=int, help='结束轮次')
    parser.add_argument('--specific-rounds', type=str, help='指定轮次列表，逗号分隔')
    parser.add_argument('--max-league-workers', type=int, default=4, help='联赛并发数')
    parser.add_argument('--max-company-workers', type=int, default=8, help='公司并发数')
    parser.add_argument('--big5-leagues', action='store_true', help='使用五大联赛ID')
    parser.add_argument('--all-36-leagues', action='store_true', help='使用所有36个联赛ID')
    
    args = parser.parse_args()
    
    # 从配置文件加载
    if args.config:
        try:
            with open(args.config, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            config = BatchProcessingConfig(**config_data)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return
    else:
        # 从命令行参数构建配置
        if args.big5_leagues:
            league_ids = [36, 31, 8, 11, 23]  # 英超、西甲、德甲、意甲、法甲
        elif args.all_36_leagues:
            # 这里需要根据实际情况定义36个联赛的ID
            league_ids = list(range(1, 37))  # 示例
        elif args.league_ids:
            try:
                league_ids = [int(lid.strip()) for lid in args.league_ids.split(',')]
            except ValueError:
                logger.error("无法解析联赛ID参数")
                return
        else:
            logger.error("请指定联赛ID")
            return
        
        specific_rounds = None
        if args.specific_rounds:
            try:
                specific_rounds = [int(r.strip()) for r in args.specific_rounds.split(',')]
            except ValueError:
                logger.error("无法解析指定轮次参数")
                return
        
        config = create_batch_config(
            league_ids=league_ids,
            season=args.season,
            start_round=args.start_round,
            end_round=args.end_round,
            specific_rounds=specific_rounds,
            max_league_workers=args.max_league_workers,
            max_company_workers=args.max_company_workers
        )
    
    # 运行批量处理
    logger.info("启动批量多轮次处理...")
    result = run_batch_processing(config)
    
    # 输出结果概要
    if result.successful_leagues == result.total_leagues:
        logger.info("🎉 所有联赛处理成功！")
    else:
        logger.warning(f"⚠️  处理完成，但有 {result.failed_leagues} 个联赛失败")


if __name__ == "__main__":
    main()