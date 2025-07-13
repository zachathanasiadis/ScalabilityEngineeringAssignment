"""
Shared cache implementation using database backend.
This ensures all app instances share the same cache data.
"""

import json
import hashlib
import threading
from typing import Any, Optional, Dict
from dataclasses import dataclass
from db.db_manager import DatabaseManager

@dataclass
class CacheStats:
    """Cache statistics"""
    hits: int = 0
    misses: int = 0
    sets: int = 0
    evictions: int = 0

class SharedCache:
    """Database-backed shared cache for multiple instances"""

    def __init__(self, default_ttl: int = 300, max_size: int = 10000):
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

        # Initialize cache table on first use
        self._ensure_cache_table()

    def _ensure_cache_table(self):
        """Create the cache table if it doesn't exist"""
        db_manager = DatabaseManager()
        if not db_manager.connect():
            print("Warning: Could not connect to database for cache initialization")
            return

        try:
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

        except Exception as e:
            print(f"Error creating cache table: {e}")
            db_manager.connection.rollback()
        finally:
            db_manager.close()

    def _generate_key(self, key: str) -> str:
        """Generate a consistent cache key"""
        return hashlib.md5(str(key).encode()).hexdigest()

    def get(self, key: str, default=None) -> Any:
        """Get value from cache"""
        cache_key = self._generate_key(key)

        with self.lock:
            db_manager = DatabaseManager()
            if not db_manager.connect():
                self.stats.misses += 1
                return default

            try:
                db_manager.cursor.execute("""
                    SELECT value_data FROM cache_entries
                    WHERE cache_key = %s AND expires_at > CURRENT_TIMESTAMP
                """, (cache_key,))

                result = db_manager.cursor.fetchone()

                if result:
                    # Update access statistics
                    db_manager.cursor.execute("""
                        UPDATE cache_entries
                        SET access_count = access_count + 1,
                            last_accessed = CURRENT_TIMESTAMP
                        WHERE cache_key = %s
                    """, (cache_key,))

                    db_manager.connection.commit()

                    try:
                        value = json.loads(result[0])
                        self.stats.hits += 1
                        return value
                    except json.JSONDecodeError:
                        self.stats.misses += 1
                        return default
                else:
                    self.stats.misses += 1
                    return default

            except Exception as e:
                print(f"Error getting cache entry: {e}")
                self.stats.misses += 1
                return default
            finally:
                db_manager.close()

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache"""
        cache_key = self._generate_key(key)
        ttl = ttl or self.default_ttl

        with self.lock:
            db_manager = DatabaseManager()
            if not db_manager.connect():
                return False

            try:
                value_data = json.dumps(value)

                db_manager.cursor.execute("""
                    INSERT INTO cache_entries (cache_key, value_data, expires_at, access_count, last_accessed)
                    VALUES (%s, %s, CURRENT_TIMESTAMP + INTERVAL '%s seconds', 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (cache_key) DO UPDATE SET
                        value_data = EXCLUDED.value_data,
                        expires_at = EXCLUDED.expires_at,
                        access_count = 1,
                        last_accessed = CURRENT_TIMESTAMP
                """, (cache_key, value_data, ttl))

                db_manager.connection.commit()
                self.stats.sets += 1

                # Periodically cleanup expired entries
                if self.stats.sets % 100 == 0:
                    self._cleanup_expired()

                return True

            except Exception as e:
                print(f"Error setting cache entry: {e}")
                db_manager.connection.rollback()
                return False
            finally:
                db_manager.close()

    def _cleanup_expired(self):
        """Remove expired cache entries"""
        db_manager = DatabaseManager()
        if not db_manager.connect():
            return

        try:
            db_manager.cursor.execute("""
                DELETE FROM cache_entries
                WHERE expires_at < CURRENT_TIMESTAMP
            """)

            deleted_count = db_manager.cursor.rowcount
            if deleted_count > 0:
                self.stats.evictions += deleted_count

            db_manager.connection.commit()

        except Exception as e:
            print(f"Error cleaning up expired cache entries: {e}")
            db_manager.connection.rollback()
        finally:
            db_manager.close()

    def clear(self):
        """Clear all cache entries"""
        with self.lock:
            db_manager = DatabaseManager()
            if not db_manager.connect():
                return

            try:
                db_manager.cursor.execute("DELETE FROM cache_entries")
                db_manager.connection.commit()

            except Exception as e:
                print(f"Error clearing cache: {e}")
                db_manager.connection.rollback()
            finally:
                db_manager.close()

    def size(self) -> int:
        """Get current cache size"""
        db_manager = DatabaseManager()
        if not db_manager.connect():
            return 0

        try:
            db_manager.cursor.execute("SELECT COUNT(*) FROM cache_entries WHERE expires_at > CURRENT_TIMESTAMP")
            result = db_manager.cursor.fetchone()
            return result[0] if result else 0
        except Exception as e:
            print(f"Error getting cache size: {e}")
            return 0
        finally:
            db_manager.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        total_requests = self.stats.hits + self.stats.misses
        hit_rate = (self.stats.hits / total_requests * 100) if total_requests > 0 else 0

        return {
            'hits': self.stats.hits,
            'misses': self.stats.misses,
            'sets': self.stats.sets,
            'evictions': self.stats.evictions,
            'hit_rate_percent': round(hit_rate, 2),
            'total_requests': total_requests,
            'current_size': self.size()
        }

# Global shared cache instance
shared_cache = SharedCache(default_ttl=300, max_size=10000)  # 5 minutes TTL, 10000 items max