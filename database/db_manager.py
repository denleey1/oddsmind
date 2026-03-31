"""Legacy database manager built on top of the new pooled connection layer."""
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from database.connection import get_connection as get_db_gateway
from database.pool import get_connection as borrow_connection

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Backward compatible database manager using the shared connection pool."""

    def __init__(self):
        self._gateway = get_db_gateway()

    def get_connection(self):
        """Expose a raw pooled connection for legacy callers."""
        return borrow_connection()

    @contextmanager
    def get_connection_context(self):
        """Legacy context manager yielding a raw connection."""
        conn = borrow_connection()
        try:
            yield conn
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def execute_sql(self, sql: str, params: Optional[tuple] = None, fetch: Optional[str] = None):
        """Execute a SQL statement with optional fetch semantics."""
        with self.get_connection_context() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, params)

                if fetch == 'all':
                    result = cursor.fetchall()
                elif fetch == 'one':
                    result = cursor.fetchone()
                elif fetch == 'many':
                    result = cursor.fetchmany()
                else:
                    conn.commit()
                    result = cursor.rowcount
            except Exception as exc:
                conn.rollback()
                logger.error("数据库操作失败: %s", exc)
                raise
            finally:
                cursor.close()

        return result
    
    def create_all_tables(self):
        """创建所有必要的表"""
        self._create_leagues_table()
        self._create_teams_table() 
        self._create_matches_table()
        self._create_standings_table()
        self._create_european_odds_table()
        self._create_european_odds_history_table()
        self._create_strength_tables()
        logger.info("所有数据表创建完成")
    
    def _create_leagues_table(self):
        """创建联赛表"""
        sql = """
        CREATE TABLE IF NOT EXISTS leagues (
            league_id INT PRIMARY KEY,
            name_cn VARCHAR(100) NOT NULL,
            name_tw VARCHAR(100),
            name_en VARCHAR(100),
            season VARCHAR(50),
            color VARCHAR(20),
            logo TEXT,
            total_rounds INT,
            current_round INT,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql)
    
    def _create_teams_table(self):
        """创建球队表"""
        sql = """
        CREATE TABLE IF NOT EXISTS teams (
            team_id INT PRIMARY KEY,
            name_cn VARCHAR(100) NOT NULL,
            name_tw VARCHAR(100),
            name_en VARCHAR(100),
            logo TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql)
    
    def _create_matches_table(self):
        """创建比赛表"""
        sql = """
        CREATE TABLE IF NOT EXISTS matches (
            match_id INT PRIMARY KEY,
            league_id INT,
            round_number INT,
            match_time VARCHAR(50),
            home_team_id INT,
            away_team_id INT,
            home_team_name VARCHAR(100),
            away_team_name VARCHAR(100),
            full_score VARCHAR(20),
            half_score VARCHAR(20),
            home_score INT,
            away_score INT,
            home_rank VARCHAR(10),
            away_rank VARCHAR(10),
            handicap DECIMAL(4,2),
            total_goals VARCHAR(10),
            match_status VARCHAR(20),
            round_status INT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_match_time (match_time),
            INDEX idx_match_league (league_id),
            FOREIGN KEY (league_id) REFERENCES leagues (league_id) ON DELETE SET NULL,
            FOREIGN KEY (home_team_id) REFERENCES teams (team_id) ON DELETE SET NULL,
            FOREIGN KEY (away_team_id) REFERENCES teams (team_id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql)
    
    def _create_standings_table(self):
        """创建积分榜表"""
        sql = """
        CREATE TABLE IF NOT EXISTS standings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            league_id INT,
            team_id INT,
            team_name VARCHAR(100),
            standing_type VARCHAR(20),
            rank_position INT,
            played INT,
            wins INT,
            draws INT,
            losses INT,
            goals_for INT,
            goals_against INT,
            goal_difference INT,
            points INT,
            recent_form VARCHAR(20),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_standings_league (league_id),
            FOREIGN KEY (league_id) REFERENCES leagues (league_id) ON DELETE SET NULL,
            FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE SET NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql)
    
    def _create_european_odds_table(self):
        """创建欧洲赔率表"""
        sql = """
        CREATE TABLE IF NOT EXISTS european_odds (
            id INT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            company_id INT NOT NULL,
            company_name VARCHAR(100),
            initial_home DECIMAL(6,3),
            initial_draw DECIMAL(6,3),
            initial_away DECIMAL(6,3),
            current_home DECIMAL(6,3),
            current_draw DECIMAL(6,3),
            current_away DECIMAL(6,3),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_match_company (match_id, company_id),
            INDEX idx_european_odds_match (match_id),
            INDEX idx_european_odds_company (company_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql)
    
    def _create_european_odds_history_table(self):
        """创建欧洲赔率历史表"""
        sql = """
        CREATE TABLE IF NOT EXISTS european_odds_history (
            id INT AUTO_INCREMENT PRIMARY KEY,
            match_id INT NOT NULL,
            company_id INT NOT NULL,
            company_name VARCHAR(100),
            home_odds DECIMAL(6,3),
            draw_odds DECIMAL(6,3),
            away_odds DECIMAL(6,3),
            change_time VARCHAR(50),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            INDEX idx_odds_history_match (match_id),
            INDEX idx_odds_history_company (company_id),
            INDEX idx_odds_history_time (change_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql)
    
    def _create_strength_tables(self):
        """创建实力相关表"""
        # 球队综合实力表
        sql1 = """
        CREATE TABLE IF NOT EXISTS team_general_strength (
            id INT AUTO_INCREMENT PRIMARY KEY,
            league_id INT,
            team_id INT,
            team_name VARCHAR(100),
            total_matches INT DEFAULT 0,
            wins INT DEFAULT 0,
            draws INT DEFAULT 0,
            losses INT DEFAULT 0,
            goals_for INT DEFAULT 0,
            goals_against INT DEFAULT 0,
            goal_difference INT DEFAULT 0,
            points INT DEFAULT 0,
            home_wins INT DEFAULT 0,
            home_draws INT DEFAULT 0,
            home_losses INT DEFAULT 0,
            away_wins INT DEFAULT 0,
            away_draws INT DEFAULT 0,
            away_losses INT DEFAULT 0,
            recent_form VARCHAR(50),
            avg_goals_for DECIMAL(4,2) DEFAULT 0,
            avg_goals_against DECIMAL(4,2) DEFAULT 0,
            win_rate DECIMAL(5,2) DEFAULT 0,
            home_win_rate DECIMAL(5,2) DEFAULT 0,
            away_win_rate DECIMAL(5,2) DEFAULT 0,
            attack_strength DECIMAL(5,2) DEFAULT 0,
            defense_strength DECIMAL(5,2) DEFAULT 0,
            overall_strength DECIMAL(5,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            UNIQUE KEY unique_league_team (league_id, team_id),
            INDEX idx_strength_league (league_id),
            INDEX idx_strength_team (team_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql1)
        
        # 联赛汇总表
        sql2 = """
        CREATE TABLE IF NOT EXISTS league_summary (
            id INT AUTO_INCREMENT PRIMARY KEY,
            league_id INT UNIQUE,
            league_name VARCHAR(100),
            total_teams INT DEFAULT 0,
            total_matches INT DEFAULT 0,
            completed_matches INT DEFAULT 0,
            avg_goals_per_match DECIMAL(4,2) DEFAULT 0,
            home_win_rate DECIMAL(5,2) DEFAULT 0,
            draw_rate DECIMAL(5,2) DEFAULT 0,
            away_win_rate DECIMAL(5,2) DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """
        self.execute_sql(sql2)

_db_manager_instance: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取数据库管理器实例（延迟初始化，避免 import 时触发数据库连接）"""
    global _db_manager_instance
    if _db_manager_instance is None:
        _db_manager_instance = DatabaseManager()
    return _db_manager_instance


def get_db_connection():
    """获取数据库连接 - 兼容旧代码"""
    return get_db_manager().get_connection()


class _LazyDatabaseManagerProxy:
    """Backward compatible lazy proxy for ``db_manager`` global symbol."""

    def __getattr__(self, item):
        return getattr(get_db_manager(), item)


# 全局数据库管理器（惰性代理）
db_manager = _LazyDatabaseManagerProxy()
