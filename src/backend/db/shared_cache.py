"""
Shared cache implementation using database backend.
This ensures all app instances share the same cache data.
"""

import json
import hashlib
import threading
import logging
import os
from typing import Any, Optional, Dict
from dataclasses import dataclass
from .connection_limiter import create_limited_connection
from datetime import datetime, timedelta

# Configure logging for cache operations
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("cache.log")
    ]
)
logger = logging.getLogger("shared_cache")

# Get app instance name for logging context
APP_NAME = os.getenv("APP_NAME", "cache-unknown")

@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0

class SharedCache:
    """Database-backed shared cache for multiple instances"""

    def __init__(self, default_ttl: int = 500000, max_size: int = 10000):
        """
        Initialize the shared cache

        Args:
            default_ttl: Default time-to-live in seconds
            max_size: Maximum number of items in cache
        """
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.stats = CacheStats()
        self.lock = threading.RLock()

        # Database connection parameters
        self.db_name = os.getenv("DB_NAME", "")
        self.db_user = os.getenv("DB_USER", "")
        self.db_password = os.getenv("DB_PASSWORD", "")
        self.db_host = os.getenv("DB_HOST", "")
        self.db_port = os.getenv("DB_PORT", "")

        logger.info(f"[{APP_NAME}] Initializing SharedCache with TTL={default_ttl}s, max_size={max_size}")

        # Initialize cache table on first use
        self._ensure_cache_table()

        logger.info(f"[{APP_NAME}] SharedCache initialization complete")

    def _get_connection(self):
        """Get a database connection with connection limiting"""
        result = create_limited_connection(
            self.db_name,
            self.db_user,
            self.db_password,
            self.db_host,
            self.db_port
        )

        if result["success"]:
            return result["connection"]
        else:
            logger.error(f"[{APP_NAME}] Could not connect to database: {result['error']}")
            return None

    def _ensure_cache_table(self):
        """Create the cache table if it doesn't exist"""
        logger.info(f"[{APP_NAME}] Ensuring cache table exists...")

        connection = self._get_connection()
        if not connection:
            logger.error(f"[{APP_NAME}] Could not connect to database for cache initialization")
            return

        try:
            with connection.cursor() as cursor:
                logger.debug(f"[{APP_NAME}] Creating cache_entries table if not exists...")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS cache_entries (
                        cache_key VARCHAR(64) PRIMARY KEY,
                        value_data TEXT NOT NULL,
                        expires_at TIMESTAMP NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        access_count INTEGER DEFAULT 0,
                        last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    );
                """)

                cursor.execute("""
                    CREATE INDEX IF NOT EXISTS idx_cache_expires
                    ON cache_entries(expires_at);
                """)

                connection.commit()
                logger.info(f"[{APP_NAME}] Cache table and index created successfully")

        except Exception as e:
            logger.error(f"[{APP_NAME}] Error creating cache table: {e}")
            connection.rollback()
        finally:
            connection.close()

    def _generate_key(self, key: str) -> str:
        """Generate a consistent cache key"""
        cache_key = hashlib.md5(str(key).encode()).hexdigest()
        logger.debug(f"[{APP_NAME}] Generated cache key: {key} -> {cache_key}")
        return cache_key

    def get(self, key: str, default=None) -> Any:
        """
        Get a value from the cache

        Args:
            key: The cache key
            default: Default value if key not found

        Returns:
            The cached value or default
        """
        with self.lock:
            cache_key = self._generate_key(key)
            logger.debug(f"[{APP_NAME}] Getting cache key: {cache_key}")

            connection = self._get_connection()
            if not connection:
                logger.error(f"[{APP_NAME}] Could not connect to database for cache get")
                return default

            try:
                with connection.cursor() as cursor:
                    # Get the cached value
                    cursor.execute("""
                        SELECT value_data, expires_at
                        FROM cache_entries
                        WHERE cache_key = %s
                    """, (cache_key,))

                    result = cursor.fetchone()

                    if result is None:
                        logger.debug(f"[{APP_NAME}] Cache miss for key: {cache_key}")
                        self.stats.misses += 1
                        return default

                    value_data, expires_at = result

                    # Check if expired
                    if expires_at < datetime.now():
                        logger.debug(f"[{APP_NAME}] Cache expired for key: {cache_key}")
                        # Clean up expired entry
                        cursor.execute("DELETE FROM cache_entries WHERE cache_key = %s", (cache_key,))
                        connection.commit()
                        self.stats.misses += 1
                        return default

                    # Update access statistics
                    cursor.execute("""
                        UPDATE cache_entries
                        SET access_count = access_count + 1, last_accessed = CURRENT_TIMESTAMP
                        WHERE cache_key = %s
                    """, (cache_key,))
                    connection.commit()

                    # Deserialize and return the value
                    try:
                        value = json.loads(value_data)
                        logger.debug(f"[{APP_NAME}] Cache hit for key: {cache_key}")
                        self.stats.hits += 1
                        return value
                    except json.JSONDecodeError as e:
                        logger.error(f"[{APP_NAME}] JSON decode error for key {cache_key}: {e}")
                        self.stats.misses += 1
                        return default

            except Exception as e:
                logger.error(f"[{APP_NAME}] Error getting cache key {cache_key}: {e}")
                self.stats.misses += 1
                return default
            finally:
                connection.close()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set a value in the cache

        Args:
            key: The cache key
            value: The value to cache
            ttl: Time-to-live in seconds (optional)

        Returns:
            True if successful, False otherwise
        """
        with self.lock:
            cache_key = self._generate_key(key)
            ttl = ttl or self.default_ttl
            expires_at = datetime.now() + timedelta(seconds=ttl)

            logger.debug(f"[{APP_NAME}] Setting cache key: {cache_key} with TTL: {ttl}s")

            connection = self._get_connection()
            if not connection:
                logger.error(f"[{APP_NAME}] Could not connect to database for cache set")
                return False

            try:
                with connection.cursor() as cursor:
                    # Serialize the value
                    try:
                        value_data = json.dumps(value)
                    except (TypeError, ValueError) as e:
                        logger.error(f"[{APP_NAME}] JSON encode error for key {cache_key}: {e}")
                        return False

                    # Check if we need to evict old entries
                    self._cleanup_expired_with_cursor(cursor)

                    # Insert or update the cache entry
                    cursor.execute("""
                        INSERT INTO cache_entries (cache_key, value_data, expires_at)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (cache_key)
                        DO UPDATE SET
                            value_data = EXCLUDED.value_data,
                            expires_at = EXCLUDED.expires_at,
                            access_count = 0,
                            last_accessed = CURRENT_TIMESTAMP
                    """, (cache_key, value_data, expires_at))

                    connection.commit()
                    self.stats.sets += 1
                    logger.debug(f"[{APP_NAME}] Successfully set cache key: {cache_key}")
                    return True

            except Exception as e:
                logger.error(f"[{APP_NAME}] Error setting cache key {cache_key}: {e}")
                connection.rollback()
                return False
            finally:
                connection.close()

    def _cleanup_expired_with_cursor(self, cursor):
        """Clean up expired entries using existing cursor"""
        try:
            cursor.execute("DELETE FROM cache_entries WHERE expires_at < CURRENT_TIMESTAMP")
            deleted_count = cursor.rowcount
            if deleted_count > 0:
                logger.debug(f"[{APP_NAME}] Cleaned up {deleted_count} expired cache entries")
                self.stats.evictions += deleted_count
        except Exception as e:
            logger.error(f"[{APP_NAME}] Error cleaning up expired entries: {e}")

    def _cleanup_expired(self):
        """Clean up expired cache entries"""
        logger.debug(f"[{APP_NAME}] Cleaning up expired cache entries...")

        connection = self._get_connection()
        if not connection:
            logger.error(f"[{APP_NAME}] Could not connect to database for cache cleanup")
            return

        try:
            with connection.cursor() as cursor:
                self._cleanup_expired_with_cursor(cursor)
                connection.commit()
        except Exception as e:
            logger.error(f"[{APP_NAME}] Error during cache cleanup: {e}")
            connection.rollback()
        finally:
            connection.close()

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            logger.info(f"[{APP_NAME}] Clearing all cache entries...")

            connection = self._get_connection()
            if not connection:
                logger.error(f"[{APP_NAME}] Could not connect to database for cache clear")
                return

            try:
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM cache_entries")
                    deleted_count = cursor.rowcount
                    connection.commit()

                    self.stats.evictions += deleted_count
                    logger.info(f"[{APP_NAME}] Cleared {deleted_count} cache entries")

            except Exception as e:
                logger.error(f"[{APP_NAME}] Error clearing cache: {e}")
                connection.rollback()
            finally:
                connection.close()

    def size(self) -> int:
        """Get the current number of cache entries"""
        connection = self._get_connection()
        if not connection:
            logger.error(f"[{APP_NAME}] Could not connect to database for cache size")
            return 0

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM cache_entries WHERE expires_at > CURRENT_TIMESTAMP")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"[{APP_NAME}] Error getting cache size: {e}")
            return 0
        finally:
            connection.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats.hits + self.stats.misses
        hit_rate = (self.stats.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "hits": self.stats.hits,
            "misses": self.stats.misses,
            "sets": self.stats.sets,
            "evictions": self.stats.evictions,
            "hit_rate": round(hit_rate, 2),
            "total_requests": total_requests,
            "current_size": self.size()
        }


# Global shared cache instance
logger.info(f"[{APP_NAME}] Creating global shared cache instance...")
shared_cache = SharedCache(default_ttl=300, max_size=10000)  # 5 minutes TTL, 10000 items max
logger.info(f"[{APP_NAME}] Global shared cache instance created")