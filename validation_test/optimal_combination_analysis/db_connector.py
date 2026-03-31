import pymysql
from typing import List, Dict, Any, Union, Tuple

class DirectDatabaseConnection:
    """
    A standalone database connection class that mimics the interface of the project's DatabaseConnection.
    Used to bypass environment configuration issues in the analysis module.
    """
    
    def __init__(self):
        # Configuration provided by user
        self.config = {
            'host': '127.0.0.1',
            'user': 'root', 
            'password': os.environ.get('MYSQL_PASSWORD', ''),
            'database': 'oddsmind',
            'charset': 'utf8mb4',
            'cursorclass': pymysql.cursors.DictCursor,
            'autocommit': True
        }
        self.connection = None
        self.connect()

    def connect(self):
        try:
            self.connection = pymysql.connect(**self.config)
            print("✅ Successfully connected to database directly.")
        except Exception as e:
            print(f"❌ Direct connection failed: {e}")
            raise

    def execute_query(self, query: str, params: Union[List, Tuple, Dict] = None, fetch: str = None) -> Any:
        """
        Executes a query and returns results based on the 'fetch' parameter.
        Mimics the interface of the project's DatabaseConnection.
        """
        if not self.connection or not self.connection.open:
            self.connect()
            
        with self.connection.cursor() as cursor:
            # Handle named parameters if necessary (pymysql supports %s, dict params with %(name)s)
            cursor.execute(query, params)
            
            if fetch == 'one':
                return cursor.fetchone()
            elif fetch == 'all':
                return cursor.fetchall()
            
            return cursor.rowcount

    def execute_many(self, query: str, data: List[Any]) -> int:
        if not self.connection or not self.connection.open:
            self.connect()
            
        with self.connection.cursor() as cursor:
            cursor.executemany(query, data)
            return cursor.rowcount
    
    def close(self):
        if self.connection and self.connection.open:
            self.connection.close()

def get_direct_connection():
    return DirectDatabaseConnection()
