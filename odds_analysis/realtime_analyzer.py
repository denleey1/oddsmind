#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
赔率分析引擎
- 核心功能：检查赔率变化并触发分析。
- 职责：作为可被外部调度的分析工具，不再作为常驻服务。
"""

import sys
from pathlib import Path
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Set, Dict, Any
from datetime import datetime, timedelta

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger
from odds_analysis.main_analyzer import MainAnalyzer
# from odds_analysis.performance_utils import (
#     LRUCache, performance_monitor, get_performance_manager
# )

# 临时替代方案：使用标准 set 和 dict
class SimpleCache:
    def __init__(self, maxsize=128):
        self._cache = {}
    def get(self, key):
        return self._cache.get(key)
    def put(self, key, value):
        self._cache[key] = value

class RealtimeOddsAnalyzer:
    """
    赔率分析引擎
    - 被动检查 odds_changes 表，分析新记录。
    - 经过重构，移除了主动监控和常驻服务逻辑。
    """
    
    def __init__(self, max_workers: int = None, max_processed_cache: int = 5000):
        """
        初始化分析引擎
        
        Args:
            max_workers: 最大并发工作线程数（如果为None，则从环境变量读取，默认16）
            max_processed_cache: 最大已处理缓存数量
        """
        import os
        if max_workers is None:
            max_workers = int(os.getenv("EXECUTOR_MAX_WORKERS", "16"))
        self.max_workers = max_workers
        self.db = get_connection()
        self.logger = get_logger(self.__class__.__name__)
        self.analyzer = MainAnalyzer()
        
        # 性能优化组件（临时禁用）
        # self.perf_manager = get_performance_manager()
        # self.memory_manager = self.perf_manager['memory_manager']
        self.processed_matches = SimpleCache(maxsize=max_processed_cache)
        self.analysis_cache = SimpleCache(maxsize=1000)
        # self.memory_manager.register_cache(self.processed_matches)
        # self.memory_manager.register_cache(self.analysis_cache)
        
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.active_tasks = set()
        
        # 性能统计
        self.stats = {
            'total_processed': 0,
            'successful_analyses': 0,
            'failed_analyses': 0,
            'cache_hits': 0,
            'start_time': datetime.now()
        }

    def batch_analyze_matches(self, match_ids: list) -> list:
        """
        批量分析指定的比赛
        
        Args:
            match_ids: 比赛ID列表
            
        Returns:
            分析结果列表
        """
        results = []
        
        try:
            self.logger.info(f"开始批量分析 {len(match_ids)} 场比赛")
            
            # [关键修复] 先过滤掉已结束的比赛
            valid_match_ids = self._filter_finished_matches(match_ids)
            
            if not valid_match_ids:
                self.logger.info("过滤后没有需要分析的比赛（所有比赛均已结束或取消）")
                return [{'match_id': mid, 'success': False, 'skipped': True, 'reason': 'match_finished'} for mid in match_ids]
            
            if len(valid_match_ids) < len(match_ids):
                skipped_count = len(match_ids) - len(valid_match_ids)
                self.logger.info(f"跳过了 {skipped_count} 场已结束的比赛，继续分析 {len(valid_match_ids)} 场比赛")
            
            # 批量分析（只分析未结束的比赛）
            self._analyze_matches_batch(set(valid_match_ids))
            
            # 等待完成
            self._wait_for_all_tasks()
            
            # 收集结果
            skipped_matches = set(match_ids) - set(valid_match_ids)
            for match_id in match_ids:
                if match_id in skipped_matches:
                    results.append({
                        'match_id': match_id,
                        'success': False,
                        'skipped': True,
                        'reason': 'match_finished'
                    })
                else:
                    results.append({
                        'match_id': match_id,
                        'success': match_id in self.processed_matches._cache,
                        'analyzed_at': datetime.now()
                    })
                
            return results
            
        except Exception as e:
            self.logger.error(f"批量分析失败: {e}", exc_info=True)
            return [{'match_id': mid, 'success': False, 'error': str(e)} for mid in match_ids]
    
    def _filter_finished_matches(self, match_ids: list) -> list:
        """
        过滤掉已结束的比赛
        
        Args:
            match_ids: 比赛ID列表
            
        Returns:
            未结束的比赛ID列表
        """
        if not match_ids:
            return []
        
        try:
            placeholders = ','.join(['%s'] * len(match_ids))
            query = f"""
                SELECT match_id
                FROM matches
                WHERE match_id IN ({placeholders})
                  AND match_status IN ('scheduled', 'live')
            """
            results = self.db.execute_query(query, match_ids, fetch='all')
            
            if not results:
                return []
            
            return [row['match_id'] for row in results]
            
        except Exception as e:
            self.logger.error(f"过滤已结束比赛失败: {e}", exc_info=True)
            # 出错时返回原列表，让后续的 MainAnalyzer 做兜底检查
            return list(match_ids)
    
    def run_analysis_on_new_changes(self, since_minutes: int = 15):
        """
        对近期发生变化的比赛进行一次性分析。
        这是该类的主要外部入口。

        Args:
            since_minutes: 检查过去多少分钟内的变化，默认为15分钟。
        """
        self.logger.info(f"开始检查过去 {since_minutes} 分钟内的赔率变化并执行分析...")
        try:
            # 1. 检查新的赔率数据
            new_matches = self._check_new_odds(since_minutes)
            
            if not new_matches:
                self.logger.info("在此期间没有发现新的赔率变化需要分析。")
                return

            # 2. 批量处理新数据
            self._analyze_matches_batch(new_matches)

            # 3. 等待所有任务完成
            self._wait_for_all_tasks()

            self.logger.info("本轮赔率变化分析完成。")

        except Exception as e:
            self.logger.error(f"分析循环出错: {e}", exc_info=True)
        finally:
            self.shutdown()
            self._log_performance_stats()

    def _wait_for_all_tasks(self):
        """等待所有活动的分析任务完成。"""
        if not self.active_tasks:
            return
            
        self.logger.info(f"等待 {len(self.active_tasks)} 个分析任务完成...")
        # 将任务列表副本传入，因为 self.active_tasks 可能会在循环中被修改
        for task in list(self.active_tasks):
            try:
                task.result(timeout=120)  # 每个任务最多等待2分钟
            except Exception as e:
                self.logger.warning(f"一个分析任务在等待完成时超时或失败: {e}")
        self.logger.info("所有分析任务均已处理完毕。")

    def shutdown(self):
        """关闭线程池并清理资源。"""
        if self.executor:
            self.executor.shutdown(wait=True)
        self.logger.info("分析引擎线程池已关闭。")

    #@performance_monitor("批量分析")
    def _analyze_matches_batch(self, match_ids: Set[int]):
        """批量并发分析比赛 (逻辑保留)"""
        unprocessed_matches = [m for m in match_ids if not self.processed_matches.get(m)]
        
        if not unprocessed_matches:
            self.logger.info("所有新变化的比赛此前均已处理过，跳过分析。")
            return
        
        self.logger.info(f"提交 {len(unprocessed_matches)} 个新比赛的分析任务到线程池...")
        
        for match_id in unprocessed_matches:
            future = self.executor.submit(self._analyze_match_with_cache, match_id)
            self.active_tasks.add(future)
        
        # 任务完成后自动清理
        for future in self.active_tasks:
            future.add_done_callback(self.active_tasks.discard)
            
    def _analyze_match_with_cache(self, match_id: int) -> bool:
        """带缓存的比赛分析 (逻辑保留)"""
        try:
            cache_key = f"analysis_{match_id}_{int(time.time() // 300)}"  # 5分钟缓存
            if self.analysis_cache.get(cache_key):
                self.stats['cache_hits'] += 1
                self.processed_matches.put(match_id, True)
                return True
            
            # MainAnalyzer.analyze_match 执行完整的分析、存储和打印流程
            # 它不返回一个简单的成功/失败字典，因此我们直接调用它
            self.analyzer.analyze_match(match_id)
            
            # 假设调用成功
            self.stats['successful_analyses'] += 1
            self.processed_matches.put(match_id, True)
            self.analysis_cache.put(cache_key, {'success': True}) # 缓存一个成功状态
            self.logger.info(f"比赛 {match_id} 分析流程已触发。")
            return True
                
        except Exception as e:
            self.stats['failed_analyses'] += 1
            self.logger.error(f"分析比赛 {match_id} 出错: {e}", exc_info=True)
            return False
        finally:
            self.stats['total_processed'] += 1
            
    def _log_performance_stats(self):
        """输出性能统计信息 (逻辑保留)"""
        uptime = datetime.now() - self.stats['start_time']
        self.logger.info(
            f"性能统计 - 总运行时长: {uptime}, "
            f"已处理: {self.stats['total_processed']}, "
            f"成功: {self.stats['successful_analyses']}, "
            f"失败: {self.stats['failed_analyses']}, "
            f"缓存命中: {self.stats['cache_hits']}"
        )
    
    def _check_new_odds(self, since_minutes: int) -> Set[int]:
        """
        检查自指定分钟前以来是否有新的赔率数据 (逻辑保留, 稍作修改)
        """
        try:
            check_since_time = datetime.now() - timedelta(minutes=since_minutes)
            query = """
                SELECT DISTINCT match_id
                FROM odds_changes
                WHERE detected_at > %s
                ORDER BY detected_at DESC
                LIMIT 500
            """
            results = self.db.execute_query(query, [check_since_time], fetch='all')
            
            if results:
                match_ids = {row['match_id'] for row in results}
                self.logger.info(f"发现 {len(match_ids)} 场比赛自 {check_since_time.strftime('%H:%M:%S')} 以来有赔率更新。")
                return match_ids
            
            return set()
            
        except Exception as e:
            self.logger.error(f"检查新赔率失败: {e}", exc_info=True)
            return set()

    # ... (移除了 get_performance_stats, get_latest_results, get_match_summary 等API类方法) ...
    # ... 这些方法更适合放在一个专门的API服务或数据查询模块中 ...

def main():
    """主函数 - 简化为命令行工具"""
    import argparse
    
    parser = argparse.ArgumentParser(description='赔率分析引擎命令行工具')
    
    subparsers = parser.add_subparsers(dest='command', required=True)

    # `run` 命令：检查并分析近期变化
    run_parser = subparsers.add_parser('run', help='检查并分析近期的赔率变化')
    run_parser.add_argument(
        '--minutes', 
        type=int, 
        default=15, 
        help='检查过去多少分钟内的变化 (默认: 15)'
    )

    # `batch` 命令：对指定的比赛列表进行一次性分析
    batch_parser = subparsers.add_parser('batch', help='批量分析指定的比赛ID')
    batch_parser.add_argument(
        'match_ids',
        nargs='+',
        type=int,
        help='要分析的比赛ID列表'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("赔率分析引擎")
    print("=" * 60)
    
    analyzer = RealtimeOddsAnalyzer()

    if args.command == 'run':
        analyzer.run_analysis_on_new_changes(since_minutes=args.minutes)
    elif args.command == 'batch':
        # 为了执行批量分析，我们可以复用 `_analyze_matches_batch`
        print(f"开始批量分析 {len(args.match_ids)} 场比赛...")
        analyzer._analyze_matches_batch(set(args.match_ids))
        analyzer._wait_for_all_tasks() # 等待完成
        analyzer.shutdown() # 关闭资源
        analyzer._log_performance_stats() # 打印统计
        print("批量分析完成。")
    
    print("分析引擎任务执行完毕。")


if __name__ == "__main__":
    main()