"""
大小球爬虫管理器 - 整合大小球爬虫和数据库操作功能
"""
import time
import sqlite3
import logging
import threading
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional
from datetime import datetime

# 添加项目路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# 使用matches_and_odds.db数据库
try:
    # 尝试从football_analysis_system.config导入
    from football_analysis_system.config import DB_MATCHES as DB_FILE
except ImportError:
    try:
        # 如果上面失败，尝试从config导入
        from config import DB_MATCHES as DB_FILE
    except ImportError:
        # 如果都导入失败，使用默认路径
        DATA_DIR = os.path.join(project_root, 'data')
        DB_FILE = os.path.join(DATA_DIR, 'matches_and_odds.db')

try:
    from scrapers.config import logger
except ImportError:
    # 设置基本日志
    import logging
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

try:
    from scrapers.overunder_scraper import OverUnderScraper
    from scrapers.overunder_database import OverUnderDatabaseManager
    from scrapers.database import DatabaseManager
except ImportError:
    # 尝试直接导入
    from overunder_scraper import OverUnderScraper
    from overunder_database import OverUnderDatabaseManager
    from database import DatabaseManager

try:
    from models.overunder_odds import OverUnderOdds
except ImportError:
    # 尝试从不同路径导入
    sys.path.append(os.path.join(project_root, 'models'))
    from overunder_odds import OverUnderOdds

class OverUnderManager:
    """大小球爬虫管理器"""
    
    def __init__(self, max_workers: int = 5, delay_between_requests: float = 1.0):
        """
        初始化大小球管理器
        
        Args:
            max_workers: 最大并发工作线程数
            delay_between_requests: 请求间延迟(秒)
        """
        self.max_workers = max_workers
        self.delay_between_requests = delay_between_requests
        
        # 创建爬虫实例
        self.scraper = OverUnderScraper()
        
        # 线程锁
        self._lock = threading.Lock()
        
        # 统计信息
        self._stats = {
            'processed_matches': 0,
            'successful_matches': 0,
            'failed_matches': 0,
            'total_odds_scraped': 0,
            'start_time': None,
            'end_time': None
        }
    
    def initialize_database(self):
        """初始化数据库表结构"""
        try:
            # 直接连接matches_and_odds.db数据库
            conn = sqlite3.connect(DB_FILE)
            
            # 创建大小球表结构
            OverUnderDatabaseManager.create_overunder_tables(conn)
            
            conn.close()
            logger.info(f"大小球数据库初始化完成: {DB_FILE}")
            
        except Exception as e:
            logger.error(f"大小球数据库初始化失败: {e}")
            raise
    
    def scrape_single_match(self, match_data: Dict[str, Any], retry_count: int = 0) -> bool:
        """
        爬取单个比赛的大小球赔率
        
        Args:
            match_data: 比赛数据字典
            retry_count: 重试次数
            
        Returns:
            bool: 是否成功
        """
        match_id = match_data['match_id']
        matchid = match_data.get('matchid', str(match_id))
        
        try:
            logger.info(f"开始爬取大小球赔率: {match_data['home_team_name']} vs {match_data['away_team_name']} (ID: {matchid})")
            
            # 获取大小球赔率
            odds_list = self.scraper.fetch_overunder_odds(matchid)
            
            if odds_list and len(odds_list) > 0:
                # 保存到数据库
                conn = sqlite3.connect(DB_FILE)
                try:
                    inserted_count = OverUnderDatabaseManager.insert_overunder_odds(
                        conn, match_id, odds_list, matchid
                    )
                    
                    # 更新爬取状态为成功
                    OverUnderDatabaseManager.update_crawl_status(
                        conn, match_id, 'success', 
                        odds_count=len(odds_list), 
                        matchid=matchid, 
                        retry_count=retry_count
                    )
                    
                    with self._lock:
                        self._stats['successful_matches'] += 1
                        self._stats['total_odds_scraped'] += len(odds_list)
                    
                    logger.info(f"成功爬取并保存 {len(odds_list)} 个大小球赔率: {matchid}")
                    return True
                    
                finally:
                    conn.close()
            else:
                # 没有获取到赔率数据
                error_msg = "未获取到大小球赔率数据"
                conn = sqlite3.connect(DB_FILE)
                try:
                    OverUnderDatabaseManager.update_crawl_status(
                        conn, match_id, 'failed', 
                        error_message=error_msg, 
                        matchid=matchid, 
                        retry_count=retry_count + 1
                    )
                finally:
                    conn.close()
                
                with self._lock:
                    self._stats['failed_matches'] += 1
                
                logger.warning(f"未获取到大小球赔率: {matchid}")
                return False
                
        except Exception as e:
            error_msg = f"爬取大小球赔率失败: {str(e)}"
            logger.error(f"{error_msg} (match_id: {matchid})")
            
            # 更新爬取状态为失败
            try:
                conn = sqlite3.connect(DB_FILE)
                try:
                    OverUnderDatabaseManager.update_crawl_status(
                        conn, match_id, 'failed', 
                        error_message=error_msg, 
                        matchid=matchid, 
                        retry_count=retry_count + 1
                    )
                finally:
                    conn.close()
            except Exception as db_e:
                logger.error(f"更新爬取状态失败: {db_e}")
            
            with self._lock:
                self._stats['failed_matches'] += 1
            
            return False
    
    def scrape_multiple_matches(self, match_list: List[Dict[str, Any]], 
                              progress_callback=None) -> Dict[str, Any]:
        """
        批量爬取多个比赛的大小球赔率
        
        Args:
            match_list: 比赛列表
            progress_callback: 进度回调函数
            
        Returns:
            Dict: 爬取结果统计
        """
        if not match_list:
            logger.warning("比赛列表为空")
            return self._stats
        
        logger.info(f"开始批量爬取 {len(match_list)} 个比赛的大小球赔率")
        
        # 重置统计信息
        with self._lock:
            self._stats.update({
                'processed_matches': 0,
                'successful_matches': 0,
                'failed_matches': 0,
                'total_odds_scraped': 0,
                'start_time': datetime.now(),
                'end_time': None
            })
        
        # 使用线程池并发处理
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_match = {}
            for i, match_data in enumerate(match_list):
                future = executor.submit(self.scrape_single_match, match_data)
                future_to_match[future] = (i, match_data)
            
            # 处理完成的任务
            for future in as_completed(future_to_match):
                index, match_data = future_to_match[future]
                
                try:
                    success = future.result()
                    
                    with self._lock:
                        self._stats['processed_matches'] += 1
                    
                    # 调用进度回调
                    if progress_callback:
                        try:
                            progress_callback(
                                self._stats['processed_matches'], 
                                len(match_list), 
                                match_data, 
                                success
                            )
                        except Exception as e:
                            logger.warning(f"进度回调函数执行失败: {e}")
                    
                    # 添加延迟以避免请求过于频繁
                    if self.delay_between_requests > 0:
                        time.sleep(self.delay_between_requests)
                        
                except Exception as e:
                    logger.error(f"处理比赛失败: {e}")
                    with self._lock:
                        self._stats['processed_matches'] += 1
                        self._stats['failed_matches'] += 1
        
        # 完成统计
        with self._lock:
            self._stats['end_time'] = datetime.now()
            duration = (self._stats['end_time'] - self._stats['start_time']).total_seconds()
            self._stats['duration_seconds'] = duration
        
        logger.info(f"批量爬取完成: 处理 {self._stats['processed_matches']} 个比赛，"
                   f"成功 {self._stats['successful_matches']} 个，"
                   f"失败 {self._stats['failed_matches']} 个，"
                   f"总计获取 {self._stats['total_odds_scraped']} 个赔率，"
                   f"耗时 {duration:.1f} 秒")
        
        return dict(self._stats)
    
    def get_pending_matches(self, limit: int = 100, force_all: bool = False) -> List[Dict[str, Any]]:
        """
        获取待爬取的比赛列表
        
        Args:
            limit: 限制数量
            force_all: 是否强制获取所有比赛
            
        Returns:
            List[Dict]: 比赛列表
        """
        try:
            conn = sqlite3.connect(DB_FILE)
            try:
                matches = OverUnderDatabaseManager.get_matches_for_overunder(
                    conn, limit=limit, force_all=force_all
                )
                return matches
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"获取待爬取比赛列表失败: {e}")
            return []
    
    def run_batch_scraping(self, limit: int = 100, force_all: bool = False, 
                          progress_callback=None) -> Dict[str, Any]:
        """
        运行批量爬取任务
        
        Args:
            limit: 限制处理的比赛数量
            force_all: 是否强制爬取所有比赛
            progress_callback: 进度回调函数
            
        Returns:
            Dict: 爬取结果统计
        """
        try:
            # 初始化数据库
            self.initialize_database()
            
            # 获取待爬取比赛
            match_list = self.get_pending_matches(limit=limit, force_all=force_all)
            
            if not match_list:
                logger.info("没有找到需要爬取大小球赔率的比赛")
                return {'message': '没有找到需要爬取的比赛'}
            
            # 执行批量爬取
            results = self.scrape_multiple_matches(match_list, progress_callback)
            
            return results
            
        except Exception as e:
            logger.error(f"批量爬取任务失败: {e}")
            return {'error': str(e)}
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        try:
            conn = sqlite3.connect(DB_FILE)
            try:
                db_stats = OverUnderDatabaseManager.get_overunder_statistics(conn)
                scraper_stats = self.scraper.get_stats()
                
                # 合并统计信息，使用正确的格式
                combined_stats = {
                    'database_stats': db_stats,  # 修改键名以匹配测试脚本的期望
                    'scraper_stats': scraper_stats,
                    'manager_stats': dict(self._stats)
                }
                
                return combined_stats
            finally:
                conn.close()
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {'error': str(e)}
    
    def test_single_match(self, match_id: str) -> Dict[str, Any]:
        """
        测试单个比赛的大小球爬取功能，并存储到数据库
        
        Args:
            match_id: 比赛ID
            
        Returns:
            Dict: 测试结果
        """
        try:
            logger.info(f"测试爬取比赛ID: {match_id}")
            
            # 获取大小球赔率
            odds_list = self.scraper.fetch_overunder_odds(match_id)
            
            if odds_list:
                # 将数据存储到数据库
                try:
                    conn = sqlite3.connect(DB_FILE)
                    try:
                        # 存储赔率数据
                        stored_count = OverUnderDatabaseManager.insert_overunder_odds(
                            conn, 
                            match_id=int(match_id), 
                            odds_list=odds_list, 
                            matchid=match_id
                        )
                        
                        # 更新爬取状态
                        OverUnderDatabaseManager.update_crawl_status(
                            conn, 
                            match_id=int(match_id), 
                            status='success', 
                            odds_count=len(odds_list),
                            matchid=match_id
                        )
                        
                        logger.info(f"成功存储 {stored_count} 条大小球赔率数据到数据库")
                        
                    finally:
                        conn.close()
                        
                except Exception as db_error:
                    logger.error(f"存储数据到数据库失败: {db_error}")
                    # 仍然返回成功，因为爬取是成功的
                
                result = {
                    'success': True,
                    'match_id': match_id,
                    'odds_count': len(odds_list),
                    'odds_data': [odds.to_dict() for odds in odds_list[:5]]  # 只返回前5个作为示例
                }
                logger.info(f"测试成功: 获取到 {len(odds_list)} 个大小球赔率")
            else:
                # 更新失败状态
                try:
                    conn = sqlite3.connect(DB_FILE)
                    try:
                        OverUnderDatabaseManager.update_crawl_status(
                            conn, 
                            match_id=int(match_id), 
                            status='failed', 
                            error_message='未获取到大小球赔率数据',
                            matchid=match_id
                        )
                    finally:
                        conn.close()
                except Exception as db_error:
                    logger.error(f"更新失败状态到数据库失败: {db_error}")
                
                result = {
                    'success': False,
                    'match_id': match_id,
                    'error': '未获取到大小球赔率数据'
                }
                logger.warning(f"测试失败: 未获取到大小球赔率数据")
            
            return result
            
        except Exception as e:
            error_msg = f"测试爬取失败: {str(e)}"
            logger.error(error_msg)
            
            # 更新错误状态
            try:
                conn = sqlite3.connect(DB_FILE)
                try:
                    OverUnderDatabaseManager.update_crawl_status(
                        conn, 
                        match_id=int(match_id), 
                        status='failed', 
                        error_message=error_msg,
                        matchid=match_id
                    )
                finally:
                    conn.close()
            except Exception as db_error:
                logger.error(f"更新错误状态到数据库失败: {db_error}")
            
            return {
                'success': False,
                'match_id': match_id,
                'error': error_msg
            }
    
    def close(self):
        """关闭管理器，清理资源"""
        if hasattr(self, 'scraper') and self.scraper:
            self.scraper.close()
        logger.info("大小球管理器已关闭") 