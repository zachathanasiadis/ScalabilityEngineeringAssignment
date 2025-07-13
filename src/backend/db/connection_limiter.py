"""
Shared connection limiting logic for database connections.
This module provides connection limiting functionality that can be used
by any component that needs to connect to the database.
"""

import os
import time
import random
import psycopg
from typing import Dict, Any


class ConnectionLimiter:
    """Handles connection limiting logic for database connections"""

    def __init__(self, conn_string: str):
        self.conn_string = conn_string
        self.max_connections = int(os.getenv("DB_MAX_CONNECTIONS", "20"))
        self.max_retries = int(os.getenv("DB_CONNECTION_RETRIES", "5"))
        self.base_backoff = float(os.getenv("DB_BASE_BACKOFF", "0.5"))

    def _get_current_connection_count(self, temp_conn) -> int:
        """Get the current number of database connections"""
        try:
            with temp_conn.cursor() as cursor:
                cursor.execute("SELECT count(*) FROM pg_stat_activity WHERE state = 'active';")
                return cursor.fetchone()[0]
        except Exception as e:
            print(f"Error getting connection count: {e}")
            return 0

    def _wait_with_backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter"""
        backoff_time = self.base_backoff * (2 ** attempt) + random.uniform(0, 0.5)
        print(f"Database connection limit reached. Backing off for {backoff_time:.2f} seconds...")
        time.sleep(backoff_time)

    def connect_with_limit(self) -> Dict[str, Any]:
        """
        Establish a database connection with connection limiting.

        Returns:
            Dict containing:
            - success: bool - Whether connection was successful
            - connection: psycopg.Connection or None - The database connection
            - error: str or None - Error message if connection failed
            - details: dict - Additional error details
        """
        for attempt in range(self.max_retries):
            try:
                # First, try to establish a temporary connection to check current connections
                temp_conn = psycopg.connect(self.conn_string)

                # Check current connection count
                current_connections = self._get_current_connection_count(temp_conn)

                if current_connections >= self.max_connections:
                    temp_conn.close()
                    print(f"Connection limit reached ({current_connections}/{self.max_connections}). Attempt {attempt + 1}/{self.max_retries}")

                    if attempt < self.max_retries - 1:
                        self._wait_with_backoff(attempt)
                        continue
                    else:
                        error_msg = f"Failed to connect after {self.max_retries} attempts. Database connection limit ({self.max_connections}) exceeded."
                        print(error_msg)
                        return {
                            "success": False,
                            "connection": None,
                            "error": error_msg,
                            "details": {
                                "current_connections": current_connections,
                                "max_connections": self.max_connections,
                                "attempts": self.max_retries
                            }
                        }

                # If we're under the limit, use the temporary connection as our main connection
                print(f"Connected to database successfully. Connections: {current_connections}/{self.max_connections}")
                return {
                    "success": True,
                    "connection": temp_conn,
                    "error": None,
                    "details": {
                        "current_connections": current_connections,
                        "max_connections": self.max_connections
                    }
                }

            except Exception as error:
                error_msg = f"Error while connecting to PostgreSQL: {error}"
                print(error_msg)

                if attempt < self.max_retries - 1:
                    print(f"Retrying connection... Attempt {attempt + 2}/{self.max_retries}")
                    self._wait_with_backoff(attempt)
                    continue
                else:
                    return {
                        "success": False,
                        "connection": None,
                        "error": str(error),
                        "details": {
                            "connection_string": self.conn_string,
                            "attempts": self.max_retries
                        }
                    }

        # This should never be reached, but added for completeness
        return {
            "success": False,
            "connection": None,
            "error": "Unexpected error: max retries exceeded without proper error handling",
            "details": {"attempts": self.max_retries}
        }


def create_limited_connection(db_name: str, db_user: str, db_password: str,
                            db_host: str, db_port: str) -> Dict[str, Any]:
    """
    Convenience function to create a limited database connection.

    Args:
        db_name: Database name
        db_user: Database user
        db_password: Database password
        db_host: Database host
        db_port: Database port

    Returns:
        Dict containing connection result (same as ConnectionLimiter.connect_with_limit)
    """
    conn_string = f"dbname={db_name} user={db_user} password={db_password} host={db_host} port={db_port}"
    limiter = ConnectionLimiter(conn_string)
    return limiter.connect_with_limit()