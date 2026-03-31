import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.append(str(PROJECT_ROOT))

from database.connection import get_connection
from core.logger import get_logger

logger = get_logger(__name__)

def check_match_id(match_id: int):
    """Checks if a match_id exists in the matches table."""
    db_conn = None
    try:
        db_conn = get_connection()
        query = "SELECT * FROM matches WHERE match_id = %s"
        result = db_conn.execute_query(query, (match_id,), fetch='one')
        
        if result:
            logger.info(f"成功在数据库中找到 match_id {match_id}。")
            # Convert Row object to dict for cleaner printing if necessary
            result_dict = dict(result) if result else {}
            logger.info(f"比赛数据: {result_dict}")
        else:
            logger.warning(f"在数据库中未能找到 match_id {match_id}。")
            
    except Exception as e:
        logger.error(f"检查 match_id {match_id} 时发生错误: {e}", exc_info=True)
    finally:
        if db_conn:
            logger.info("数据库检查脚本执行完毕。")


if __name__ == "__main__":
    target_match_id = 2702235
    logger.info(f"开始检查 match_id: {target_match_id}")
    check_match_id(target_match_id)