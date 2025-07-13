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
from db.db_manager import DatabaseManager
from datetime import datetime, timedelta, timezone

# Configure logging for cache operations
logging.basicConfig(
    level=logging.INFO,
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

        logger.info(f"[{APP_NAME}] Initializing SharedCache with TTL={default_ttl}s, max_size={max_size}")

        # Initialize cache table on first use
        self._ensure_cache_table()

        logger.info(f"[{APP_NAME}] SharedCache initialization complete")

    def _ensure_cache_table(self):
        """Create the cache table if it doesn't exist"""
        logger.info(f"[{APP_NAME}] Ensuring cache table exists...")

        db_manager = DatabaseManager()
        connection_result = db_manager.connect()
        if not connection_result["success"]:
            logger.error(f"[{APP_NAME}] Could not connect to database for cache initialization: {connection_result['error']}")
            return

        try:
            logger.debug(f"[{APP_NAME}] Creating cache_entries table if not exists...")
            db_manager.cursor.execute("""
                CREATE TABLE IF NOT EXISTS cache_entries (
                    cache_key VARCHAR(64) PRIMARY KEY,
                    value_data TEXT NOT NULL,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    access_count INTEGER DEFAULT 0,
                    last_accessed TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            db_manager.cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cache_expires
                ON cache_entries(expires_at);
            """)

            db_manager.connection.commit()
            logger.info(f"[{APP_NAME}] Cache table and index created successfully")

        except Exception as e:
            logger.error(f"[{APP_NAME}] Error creating cache table: {e}")
            db_manager.connection.rollback()
        finally:
            db_manager.close()

    def _generate_key(self, key: str) -> str:
        """Generate a consistent cache key"""
        cache_key = hashlib.md5(str(key).encode()).hexdigest()
        logger.debug(f"[{APP_NAME}] Generated cache key: {key} -> {cache_key}")
        return cache_key

    def get(self, key: str, default=None) -> Any:
        """Get value from cache"""
        logger.debug(f"[{APP_NAME}] Cache GET request for key: {key}")
        cache_key = self._generate_key(key)

        with self.lock:
            db_manager = DatabaseManager()
            connection_result = db_manager.connect()
            if not connection_result["success"]:
                logger.error(f"[{APP_NAME}] Cache GET failed - DB connection error: {connection_result['error']}")
                self.stats.misses += 1
                return default

            try:
                # Query cache entry
                logger.debug(f"[{APP_NAME}] Querying cache for key: {cache_key}")
                db_manager.cursor.execute("""
                    SELECT value_data, expires_at, access_count FROM cache_entries
                    WHERE cache_key = %s
                """, (cache_key,))

                result = db_manager.cursor.fetchone()
                logger.debug(f"[{APP_NAME}] Query result: {result is not None}")

                if result:
                    value_data, expires_at, access_count = result
                    logger.debug(f"[{APP_NAME}] Found cache entry - expires_at: {expires_at}, access_count: {access_count}")

                    # Check if expired
                    if expires_at and expires_at < datetime.now():
                        logger.info(f"[{APP_NAME}] Cache entry EXPIRED for key: {key} (expired at {expires_at})")
                        self.stats.misses += 1
                        return default

                    # Update access statistics
                    logger.debug(f"[{APP_NAME}] Updating access statistics for key: {cache_key}")
                    db_manager.cursor.execute("""
                        UPDATE cache_entries
                        SET access_count = access_count + 1,
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE cache_key = %s
                    """, (cache_key,))

                    db_manager.connection.commit()

                    try:
                        value = json.loads(value_data)
                        self.stats.hits += 1
                        logger.info(f"[{APP_NAME}] Cache HIT for key: {key} (access_count: {access_count + 1})")
                        return value
                    except json.JSONDecodeError as e:
                        logger.error(f"[{APP_NAME}] Cache data corruption for key: {key} - {e}")
                        self.stats.misses += 1
                        return default
                else:
                    self.stats.misses += 1
                    logger.info(f"[{APP_NAME}] Cache MISS for key: {key} (not found in database)")
                    return default

            except Exception as e:
                logger.error(f"[{APP_NAME}] Error getting cache entry for key '{key}': {e}")
                self.stats.misses += 1
                return default
            finally:
                db_manager.close()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        ttl = ttl or self.default_ttl
        logger.debug(f"[{APP_NAME}] Cache SET request for key: {key} with TTL: {ttl}s")

        cache_key = self._generate_key(key)

        with self.lock:
            db_manager = DatabaseManager()
            connection_result = db_manager.connect()
            if not connection_result["success"]:
                logger.error(f"[{APP_NAME}] Cache SET failed - DB connection error: {connection_result['error']}")
                return False

            try:
                value_data = json.dumps(value)
                expires_at = datetime.now() + timedelta(seconds=ttl)

                logger.debug(f"[{APP_NAME}] Setting cache entry - key: {cache_key}, expires_at: {expires_at}")

                db_manager.cursor.execute("""
                    INSERT INTO cache_entries (cache_key, value_data, expires_at, access_count, last_accessed)
                    VALUES (%s, %s, %s, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        value_data = EXCLUDED.value_data,
                        expires_at = EXCLUDED.expires_at,
                        access_count = 1,
                        last_accessed = CURRENT_TIMESTAMP
                """, (cache_key, value_data, expires_at))

                db_manager.connection.commit()
                self.stats.sets += 1
                logger.info(f"[{APP_NAME}] Cache SET successful for key: {key} (TTL: {ttl}s, expires: {expires_at})")

                # Periodically cleanup expired entries
                if self.stats.sets % 100 == 0:
                    logger.info(f"[{APP_NAME}] Triggering periodic cleanup (sets: {self.stats.sets})")
                    self._cleanup_expired()

                return True

            except Exception as e:
                logger.error(f"[{APP_NAME}] Error setting cache entry for key '{key}': {e}")
                db_manager.connection.rollback()
                return False
            finally:
                db_manager.close()

    def _cleanup_expired(self):
        """Remove expired cache entries"""
        logger.info(f"[{APP_NAME}] Starting cleanup of expired cache entries...")

        db_manager = DatabaseManager()
        connection_result = db_manager.connect()
        if not connection_result["success"]:
            logger.error(f"[{APP_NAME}] Cleanup failed - DB connection error: {connection_result['error']}")
            return

        try:
            # First, count expired entries
            db_manager.cursor.execute("""
                SELECT COUNT(*) FROM cache_entries
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            expired_count = db_manager.cursor.fetchone()[0]

            if expired_count > 0:
                logger.info(f"[{APP_NAME}] Found {expired_count} expired cache entries to clean up")

                db_manager.cursor.execute("""
                    DELETE FROM cache_entries
                    WHERE expires_at < CURRENT_TIMESTAMP
                """)

                deleted_count = db_manager.cursor.rowcount
                if deleted_count > 0:
                    self.stats.evictions += deleted_count
                    logger.info(f"[{APP_NAME}] Cleaned up {deleted_count} expired cache entries")

                db_manager.connection.commit()
            else:
                logger.debug(f"[{APP_NAME}] No expired cache entries found")

        except Exception as e:
            logger.error(f"[{APP_NAME}] Error cleaning up expired cache entries: {e}")
            db_manager.connection.rollback()
        finally:
            db_manager.close()

    def clear(self):
        """Clear all cache entries"""
        logger.info(f"[{APP_NAME}] Clearing all cache entries...")

        with self.lock:
            db_manager = DatabaseManager()
            connection_result = db_manager.connect()
            if not connection_result["success"]:
                logger.error(f"[{APP_NAME}] Clear failed - DB connection error: {connection_result['error']}")
                return

            try:
                # Count entries before clearing
                db_manager.cursor.execute("SELECT COUNT(*) FROM cache_entries")
                count_before = db_manager.cursor.fetchone()[0]

                db_manager.cursor.execute("DELETE FROM cache_entries")
                db_manager.connection.commit()

                logger.info(f"[{APP_NAME}] Cleared {count_before} cache entries")

            except Exception as e:
                logger.error(f"[{APP_NAME}] Error clearing cache: {e}")
                db_manager.connection.rollback()
            finally:
                db_manager.close()

    def size(self) -> int:
        """Get current cache size"""
        logger.debug(f"[{APP_NAME}] Getting cache size...")

        db_manager = DatabaseManager()
        connection_result = db_manager.connect()
        if not connection_result["success"]:
            logger.error(f"[{APP_NAME}] Size check failed - DB connection error: {connection_result['error']}")
            return 0

        try:
            db_manager.cursor.execute("SELECT COUNT(*) FROM cache_entries WHERE expires_at > CURRENT_TIMESTAMP")
            result = db_manager.cursor.fetchone()
            size = result[0] if result else 0
            logger.debug(f"[{APP_NAME}] Current cache size: {size} entries")
            return size
        except Exception as e:
            logger.error(f"[{APP_NAME}] Error getting cache size: {e}")
            return 0
        finally:
            db_manager.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats.hits + self.stats.misses
        hit_rate = (self.stats.hits / total_requests * 100) if total_requests > 0 else 0

        current_size = self.size()

        stats = {
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'sets': self.stats.sets,
            'evictions': self.stats.evictions,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests,
            'current_size': current_size
        }

        logger.info(f"[{APP_NAME}] Cache stats: {stats}")
        return stats

# Global shared cache instance
logger.info(f"[{APP_NAME}] Creating global shared cache instance...")
shared_cache = SharedCache(default_ttl=300, max_size=10000)  # 5 minutes TTL, 10000 items max
logger.info(f"[{APP_NAME}] Global shared cache instance created")