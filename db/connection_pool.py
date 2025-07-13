"""
Database Connection Pool Manager
Prevents database overloading by limiting concurrent connections
"""

import threading
import time
from queue import Queue, Empty
from contextlib import contextmanager
from db.db_manager import DatabaseManager

class ConnectionPool:
    """Thread-safe database connection pool"""

    def __init__(self, max_connections=10, timeout=30):
        self.max_connections = max_connections
        self.timeout = timeout
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        self.active_connections = 0
        self.total_connections = 0

        # Pre-populate pool with connections
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool with connections"""
        for _ in range(self.max_connections):
            try:
                db_manager = DatabaseManager()
                if db_manager.connect():
                    self.pool.put(db_manager)
                    self.total_connections += 1
                else:
                    print(f"Failed to create connection {_ + 1}")
            except Exception as e:
                print(f"Error creating connection {_ + 1}: {e}")

    @contextmanager
    def get_connection(self):
        """Get a database connection from the pool"""
        connection = None
        try:
            # Get connection from pool with timeout
            connection = self.pool.get(timeout=self.timeout)
            with self.lock:
                self.active_connections += 1

            # Verify connection is still valid
            if not connection.connection or connection.connection.closed:
                connection.connect()

            yield connection

        except Empty:
            raise Exception("Connection pool exhausted - all connections in use")
        except Exception as e:
            print(f"Error getting connection: {e}")
            raise
        finally:
            if connection:
                with self.lock:
                    self.active_connections -= 1
                # Return connection to pool
                self.pool.put(connection)

    def get_stats(self):
        """Get connection pool statistics"""
        return {
            "total_connections": self.total_connections,
            "active_connections": self.active_connections,
            "available_connections": self.pool.qsize(),
            "max_connections": self.max_connections
        }

    def close_all(self):
        """Close all connections in the pool"""
        while not self.pool.empty():
            try:
                conn = self.pool.get_nowait()
                conn.close()
            except Empty:
                break

# Global connection pool instance
connection_pool = ConnectionPool(max_connections=10, timeout=30)