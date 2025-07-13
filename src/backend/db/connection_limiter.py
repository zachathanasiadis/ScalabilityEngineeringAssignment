"""
Shared connection limiting logic for database connections.
This module provides connection limiting functionality that can be used
by any component that needs to connect to the database.
"""

import os
import time
import random
import logging
import psycopg
from typing import Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("connection_limiter.log")
    ]
)
logger = logging.getLogger(__name__)


class ConnectionLimiter:
    """Handles connection limiting logic for database connections"""

    def __init__(self, conn_string: str):
        self.conn_string = conn_string
        self.base_backoff = float(os.getenv("DB_BASE_BACKOFF", "0.5"))
        self.max_retries = int(os.getenv("DB_CONNECTION_RETRIES", "5"))

    def _is_connection_limit_error(self, error: Exception) -> bool:
        """Check if the error is due to connection limit being exceeded"""
        error_str = str(error).lower()
        connection_limit_messages = [
            "too many connections for role"
        ]
        return any(msg in error_str for msg in connection_limit_messages)

    def _wait_with_backoff(self, attempt: int) -> None:
        """Exponential backoff with jitter"""
        backoff_time = self.base_backoff * (2 ** attempt) + random.uniform(0, 1)

        logger.info(f"Database connection limit reached. Backing off for {backoff_time:.2f} seconds... (attempt {attempt + 1})")
        time.sleep(backoff_time)

    def connect_with_limit(self) -> Dict[str, Any]:
        """
        Establish a database connection with connection limiting.

        This method relies on PostgreSQL's built-in max_connections limit.
        When the limit is exceeded, PostgreSQL refuses the connection with
        an error message, which we catch and handle with backoff.

        Returns:
            Dict containing:
            - success: bool - Whether connection was successful
            - connection: psycopg.Connection or None - The database connection
            - error: str or None - Error message if connection failed
            - details: dict - Additional error details
        """

        for attempt in range(self.max_retries):
            try:
                # Attempt to connect directly - let PostgreSQL handle the limiting
                conn = psycopg.connect(self.conn_string)

                logger.info(f"Connected to database successfully on attempt {attempt + 1}")
                return {
                    "connection": conn,
                    "error": None
                }

            except Exception as error:
                error_msg = f"Error while connecting to PostgreSQL: {error}"
                logger.error(error_msg)

                # Check if this is a connection limit error
                if self._is_connection_limit_error(error):
                    logger.info(f"Connection limit reached. Attempt {attempt + 1}/{self.max_retries}")

                    if attempt < self.max_retries - 1:
                        self._wait_with_backoff(attempt)
                        continue
                    else:
                        error_msg = f"Failed to connect after {self.max_retries} attempts. PostgreSQL connection limit exceeded."
                        logger.error(error_msg)
                        return {
                            "connection": None,
                            "error": "connection_limit_exceeded",
                        }
                else:
                    # For non-connection-limit errors, still retry but with different handling
                    logger.info(f"Non-connection-limit error occurred. Attempt {attempt + 1}/{self.max_retries}")

                    if attempt < self.max_retries - 1:
                        # Shorter backoff for non-connection-limit errors
                        time.sleep(self.base_backoff + random.uniform(0, 1))
                        continue
                    else:
                        return {
                            "connection": None,
                            "error": "connection_error"
                        }
        return {
            "connection": None,
            "error": "uknown_database_error"
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