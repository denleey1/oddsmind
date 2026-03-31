"""
大小球数据库模块 - 包含大小球赔率数据的数据库操作功能
"""
import sqlite3
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import List, Optional, Dict, Any

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
    from models.overunder_odds import OverUnderOdds
except ImportError:
    # 尝试从不同路径导入
    sys.path.append(os.path.join(project_root, 'models'))
    from overunder_odds import OverUnderOdds

class OverUnderDatabaseManager:
    """大小球数据库管理类，处理大小球赔率数据的数据库操作"""
    
    @staticmethod
    def create_overunder_tables(conn: sqlite3.Connection):
        """
        创建大小球相关数据库表结构
        
        Args:
            conn: 数据库连接对象
        """
        cursor = conn.cursor()
        
        try:
            # 禁用外键约束，以避免插入错误
            cursor.execute("PRAGMA foreign_keys = OFF;")
            
            # 检查数据库中的所有表
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # 创建大小球赔率表（如果不存在）
            if "overunder_odds" not in tables:
                logger.info("创建overunder_odds表...")
                cursor.execute('''
                CREATE TABLE overunder_odds (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,      /* 自增ID */
                    match_id INTEGER NOT NULL,                 /* 比赛ID */
                    matchid TEXT,                              /* 比赛ID(字符串格式) */
                    company_id TEXT,                           /* 博彩公司ID */
                    company_name TEXT NOT NULL,                /* 博彩公司名称 */
                    initial_over REAL,                         /* 初始大球赔率 */
                    initial_line TEXT,                         /* 初始盘口（字符串） */
                    initial_under REAL,                        /* 初始小球赔率 */
                    instant_over REAL,                         /* 即时大球赔率 */
                    instant_line TEXT,                         /* 即时盘口（字符串） */
                    instant_under REAL,                        /* 即时小球赔率 */
                    line_numeric REAL,                         /* 盘口数值 */
                    update_time TEXT NOT NULL,                 /* 更新时间 */
                    crawl_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP, /* 爬取时间 */
                    UNIQUE (match_id, company_id, update_time) /* 防止重复数据 */
                )
                ''')
                
                # 创建overunder_odds表索引
                cursor.execute('CREATE INDEX idx_overunder_match_id ON overunder_odds(match_id)')
                cursor.execute('CREATE INDEX idx_overunder_matchid ON overunder_odds(matchid)')
                cursor.execute('CREATE INDEX idx_overunder_company_id ON overunder_odds(company_id)')
                cursor.execute('CREATE INDEX idx_overunder_company_name ON overunder_odds(company_name)')
                cursor.execute('CREATE INDEX idx_overunder_line_numeric ON overunder_odds(line_numeric)')
                cursor.execute('CREATE INDEX idx_overunder_crawl_time ON overunder_odds(crawl_time)')
                cursor.execute('CREATE INDEX idx_overunder_update_time ON overunder_odds(update_time)')
                
                logger.info("overunder_odds表创建成功")
            else:
                # 如果表已存在，检查是否需要添加新字段
                cursor.execute("PRAGMA table_info(overunder_odds)")
                columns = cursor.fetchall()
                column_names = [column[1] for column in columns]
                
                # 检查是否有line_numeric字段
                if 'line_numeric' not in column_names:
                    logger.info("向overunder_odds表添加line_numeric字段...")
                    cursor.execute("ALTER TABLE overunder_odds ADD COLUMN line_numeric REAL")
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_overunder_line_numeric ON overunder_odds(line_numeric)')
                
                # 检查是否有crawl_time字段
                if 'crawl_time' not in column_names:
                    logger.info("向overunder_odds表添加crawl_time字段...")
                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute(f"ALTER TABLE overunder_odds ADD COLUMN crawl_time TEXT DEFAULT '{current_time}'")
                    cursor.execute('CREATE INDEX IF NOT EXISTS idx_overunder_crawl_time ON overunder_odds(crawl_time)')
            
            # 创建大小球爬取状态表（如果不存在）
            if "overunder_crawl_status" not in tables:
                logger.info("创建overunder_crawl_status表...")
                cursor.execute('''
                CREATE TABLE overunder_crawl_status (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id INTEGER UNIQUE NOT NULL,          /* 比赛ID */
                    matchid TEXT,                              /* 比赛ID(字符串格式) */
                    status TEXT DEFAULT 'pending',             /* 爬取状态：pending, success, failed, skipped */
                    retry_count INTEGER DEFAULT 0,             /* 重试次数 */
                    last_attempt_time TEXT,                    /* 最后尝试时间 */
                    success_time TEXT,                         /* 成功时间 */
                    error_message TEXT,                        /* 错误信息 */
                    odds_count INTEGER DEFAULT 0,             /* 获取到的赔率数量 */
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                ''')
                
                # 创建overunder_crawl_status表索引
                cursor.execute('CREATE INDEX idx_overunder_status_match_id ON overunder_crawl_status(match_id)')
                cursor.execute('CREATE INDEX idx_overunder_status_matchid ON overunder_crawl_status(matchid)')
                cursor.execute('CREATE INDEX idx_overunder_status_status ON overunder_crawl_status(status)')
                cursor.execute('CREATE INDEX idx_overunder_status_timestamp ON overunder_crawl_status(timestamp)')
                
                logger.info("overunder_crawl_status表创建成功")
            
            conn.commit()
            logger.info("大小球数据库表结构检查/创建完成")
            
        except sqlite3.Error as e:
            logger.error(f"创建大小球数据库表失败: {e}")
            logger.error(traceback.format_exc())
            if conn:
                conn.rollback()
            raise
    
    @staticmethod
    def insert_overunder_odds(conn: sqlite3.Connection, match_id: int, odds_list: List[OverUnderOdds], 
                            matchid: str = None) -> int:
        """
        插入大小球赔率数据
        
        Args:
            conn: 数据库连接对象
            match_id: 比赛ID
            odds_list: 大小球赔率列表
            matchid: 比赛ID(字符串格式)
            
        Returns:
            int: 插入的记录数
        """
        if not odds_list:
            logger.warning("大小球赔率列表为空，跳过插入")
            return 0
        
        cursor = conn.cursor()
        inserted_count = 0
        
        try:
            for odds in odds_list:
                # 检查是否已存在相同数据
                cursor.execute('''
                SELECT id FROM overunder_odds 
                WHERE match_id = ? AND company_id = ? AND update_time = ?
                ''', (match_id, odds.company_id, odds.update_time))
                
                if cursor.fetchone():
                    logger.debug(f"跳过重复的大小球赔率数据: match_id={match_id}, company_id={odds.company_id}")
                    continue
                
                # 插入大小球赔率数据
                cursor.execute('''
                INSERT INTO overunder_odds (
                    match_id, matchid, company_id, company_name,
                    initial_over, initial_line, initial_under,
                    instant_over, instant_line, instant_under,
                    line_numeric, update_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    match_id, matchid, odds.company_id, odds.bookmaker,
                    odds.initial_over, odds.initial_line, odds.initial_under,
                    odds.instant_over, odds.instant_line, odds.instant_under,
                    odds.line_numeric, odds.update_time
                ))
                
                inserted_count += 1
                logger.debug(f"插入大小球赔率: {odds.bookmaker} - {odds.instant_line}")
            
            conn.commit()
            logger.info(f"成功插入 {inserted_count} 条大小球赔率数据")
            
        except sqlite3.Error as e:
            logger.error(f"插入大小球赔率数据失败: {e}")
            logger.error(traceback.format_exc())
            conn.rollback()
            raise
        
        return inserted_count
    
    @staticmethod
    def update_crawl_status(conn: sqlite3.Connection, match_id: int, status: str, 
                          error_message: str = None, odds_count: int = 0, 
                          matchid: str = None, retry_count: int = 0):
        """
        更新大小球爬取状态
        
        Args:
            conn: 数据库连接对象
            match_id: 比赛ID
            status: 爬取状态
            error_message: 错误信息
            odds_count: 赔率数量
            matchid: 比赛ID(字符串格式)
            retry_count: 重试次数
        """
        cursor = conn.cursor()
        
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 检查是否已存在记录
            cursor.execute('SELECT id FROM overunder_crawl_status WHERE match_id = ?', (match_id,))
            existing = cursor.fetchone()
            
            if existing:
                # 更新现有记录
                if status == 'success':
                    cursor.execute('''
                    UPDATE overunder_crawl_status 
                    SET status = ?, success_time = ?, odds_count = ?, 
                        error_message = ?, retry_count = ?, timestamp = ?
                    WHERE match_id = ?
                    ''', (status, current_time, odds_count, error_message, retry_count, current_time, match_id))
                else:
                    cursor.execute('''
                    UPDATE overunder_crawl_status 
                    SET status = ?, last_attempt_time = ?, error_message = ?, 
                        retry_count = ?, timestamp = ?
                    WHERE match_id = ?
                    ''', (status, current_time, error_message, retry_count, current_time, match_id))
            else:
                # 插入新记录
                if status == 'success':
                    cursor.execute('''
                    INSERT INTO overunder_crawl_status 
                    (match_id, matchid, status, success_time, odds_count, error_message, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (match_id, matchid, status, current_time, odds_count, error_message, retry_count))
                else:
                    cursor.execute('''
                    INSERT INTO overunder_crawl_status 
                    (match_id, matchid, status, last_attempt_time, error_message, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ''', (match_id, matchid, status, current_time, error_message, retry_count))
            
            conn.commit()
            logger.debug(f"更新大小球爬取状态: match_id={match_id}, status={status}")
            
        except sqlite3.Error as e:
            logger.error(f"更新大小球爬取状态失败: {e}")
            conn.rollback()
            raise
    
    @staticmethod
    def get_matches_for_overunder(conn: sqlite3.Connection, limit: int = 100, 
                                force_all: bool = False) -> List[Dict[str, Any]]:
        """
        获取需要爬取大小球赔率的比赛列表
        
        Args:
            conn: 数据库连接对象
            limit: 限制返回数量
            force_all: 是否强制获取所有比赛
            
        Returns:
            List[Dict]: 比赛列表
        """
        cursor = conn.cursor()
        
        try:
            if force_all:
                # 获取所有比赛
                cursor.execute('''
                SELECT m.match_id, m.match_id as matchid, m.league_name, m.home_team, 
                       m.away_team, m.start_time, 0 as match_status
                FROM matches m
                ORDER BY m.start_time DESC
                LIMIT ?
                ''', (limit,))
            else:
                # 获取未爬取或失败的比赛
                cursor.execute('''
                SELECT m.match_id, m.match_id as matchid, m.league_name, m.home_team, 
                       m.away_team, m.start_time, 0 as match_status,
                       COALESCE(ocs.status, 'pending') as crawl_status,
                       COALESCE(ocs.retry_count, 0) as retry_count
                FROM matches m
                LEFT JOIN overunder_crawl_status ocs ON m.match_id = ocs.match_id
                WHERE (ocs.status IS NULL OR ocs.status IN ('pending', 'failed'))
                  AND ocs.retry_count < 3
                ORDER BY m.start_time DESC
                LIMIT ?
                ''', (limit,))
            
            matches = []
            for row in cursor.fetchall():
                match_data = {
                    'match_id': row[0],
                    'matchid': row[1],
                    'league_name': row[2],
                    'home_team_name': row[3],
                    'away_team_name': row[4],
                    'match_time': row[5],
                    'match_status': row[6]
                }
                
                if not force_all and len(row) > 7:
                    match_data['crawl_status'] = row[7]
                    match_data['retry_count'] = row[8]
                
                matches.append(match_data)
            
            logger.info(f"获取到 {len(matches)} 个需要爬取大小球赔率的比赛")
            return matches
            
        except sqlite3.Error as e:
            logger.error(f"获取大小球爬取比赛列表失败: {e}")
            return []
    
    @staticmethod
    def get_overunder_statistics(conn: sqlite3.Connection) -> Dict[str, Any]:
        """
        获取大小球数据统计信息
        
        Args:
            conn: 数据库连接对象
            
        Returns:
            Dict: 统计信息
        """
        cursor = conn.cursor()
        stats = {}
        
        try:
            # 总赔率数量
            cursor.execute('SELECT COUNT(*) FROM overunder_odds')
            stats['total_odds'] = cursor.fetchone()[0]
            
            # 总比赛数量
            cursor.execute('SELECT COUNT(DISTINCT match_id) FROM overunder_odds')
            stats['total_matches'] = cursor.fetchone()[0]
            
            # 博彩公司数量
            cursor.execute('SELECT COUNT(DISTINCT company_name) FROM overunder_odds')
            stats['total_companies'] = cursor.fetchone()[0]
            
            # 爬取状态统计
            cursor.execute('''
            SELECT status, COUNT(*) 
            FROM overunder_crawl_status 
            GROUP BY status
            ''')
            stats['crawl_status'] = dict(cursor.fetchall())
            
            # 最新更新时间
            cursor.execute('SELECT MAX(crawl_time) FROM overunder_odds')
            latest_time = cursor.fetchone()[0]
            stats['latest_update'] = latest_time
            
            logger.info(f"大小球数据统计: {stats}")
            return stats
            
        except sqlite3.Error as e:
            logger.error(f"获取大小球统计信息失败: {e}")
            return stats 