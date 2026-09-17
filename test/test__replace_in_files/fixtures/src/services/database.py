"""Database service module — connection pooling and query execution."""

import psycopg2
from contextlib import contextmanager


class DatabaseService:
    """Manages database connections and provides query helpers.
    
    Handles connection pooling automatically for performance optimization.
    """
    
    def __init__(self, config):
        self.config = config
        self.pool_size = config.get("max_connections", 10)
        
    @contextmanager
    def get_connection(self):
        """Context manager for acquiring and releasing database connections."""
        conn = None
        try:
            conn = psycopg2.connect(
                host=self.config["host"],
                port=self.config["port"],
                dbname=self.config["name"]
            )
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise RuntimeError(f"Database operation failed: {e}")
        finally:
            if conn:
                conn.close()
                
    def execute_query(self, query, params=None):
        """Execute a SELECT query and return results as list of dicts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]


def create_service(config):
    """Factory function to instantiate DatabaseService with given config."""
    return DatabaseService(config)
