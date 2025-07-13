from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import logging
from queue_service.queue_manager import TaskQueue
from db.db_manager import DatabaseManager
from typing import Dict, Any, Optional, Tuple, Union
from contextlib import contextmanager

# Custom exceptions
class ConnectionLimitExceeded(Exception):
    """Raised when database connection limit is exceeded"""
    pass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)
logger = logging.getLogger(__name__)

# Get app instance name from environment
APP_NAME = os.getenv("APP_NAME", "hash-api-unknown")
logger.info(f"=== Starting {APP_NAME} ===")

try:
    from db.shared_cache import shared_cache
    logger.info(f"[{APP_NAME}] Successfully initialized shared cache")
except Exception as e:
    logger.error(f"[{APP_NAME}] Warning: Could not initialize shared cache: {e}")
    # Create a dummy cache that does nothing
    class DummyCache:
        def get(self, key, default=None):
            return default
        def set(self, key, value, ttl=None):
            return False
        def clear(self):
            return True
        def get_stats(self):
            return {"hits": 0, "misses": 0, "sets": 0, "evictions": 0}
    shared_cache = DummyCache()
    logger.info(f"[{APP_NAME}] Using dummy cache as fallback")

import json

app = FastAPI(title=f"{APP_NAME} Hash API")

# Initialize these only once
logger.info(f"[{APP_NAME}] Initializing database manager and task queue")
db_manager = DatabaseManager()
task_queue = TaskQueue(db_manager)

# Create tables if they don't exist
logger.info(f"[{APP_NAME}] Attempting to connect to database for table creation")
connection_result = db_manager.connect()
if not connection_result["error"]:
    logger.info(f"[{APP_NAME}] Database connection successful, creating tables")
    db_manager.create_tables()
    db_manager.close()
    logger.info(f"[{APP_NAME}] Database tables created successfully")
else:
    logger.error(f"[{APP_NAME}] Failed to connect to database at startup: {connection_result['error']}")

logger.info(f"[{APP_NAME}] Application initialization complete")


class InputString(BaseModel):
    string: str


# Shared utility functions
def check_cache(hash_type: str, string: str) -> Optional[Dict[str, Any]]:
    """Check if result exists in cache and return it"""
    cache_key = f"{hash_type}:{string}"
    cached_result = shared_cache.get(cache_key)

    if cached_result:
        logger.info(f"[{APP_NAME}] {hash_type.upper()} result found in cache for string: {string}")
        return {"result": cached_result, "source": "cache"}

    return None


def cache_result(hash_type: str, result: Dict[str, Any], ttl: int = 3600) -> None:
    """Cache a completed result"""
    original_string = result.get('original_string')
    if not original_string:
        return

    cache_key = f"{hash_type}:{original_string}"
    shared_cache.set(cache_key, result, ttl=ttl)
    logger.info(f"[{APP_NAME}] Cached {hash_type.upper()} hash for string: {original_string}")


@contextmanager
def get_database_connection():
    """Context manager for database connections"""
    logger.info(f"[{APP_NAME}] Attempting to get database connection...")
    connection_result = db_manager.connect()
    logger.info(f"[{APP_NAME}] Database connection attempt result: success={connection_result['success']}")

    if connection_result["error"]:
        logger.error(f"[{APP_NAME}] Database connection failed: {connection_result['error']}")
        raise HTTPException(status_code=500, detail=f"Database connection failed: {connection_result['error']}")

    logger.info(f"[{APP_NAME}] Database connection successful, entering context")
    try:
        yield db_manager
    finally:
        logger.info(f"[{APP_NAME}] Closing database connection")
        db_manager.close()


def add_task(request_type: str, string: str) -> Union[Dict[str, Any], JSONResponse]:
    """Add a hash task to the queue"""
    logger.info(f"[{APP_NAME}] add_task() called for {request_type.upper()}: {string}")
    try:
        with get_database_connection() as db:
            logger.info(f"[{APP_NAME}] Inside database context, adding task to queue for {request_type.upper()}: {string}")
            task_id = task_queue.add_task(request_type, {'string': string})
            logger.info(f"[{APP_NAME}] Task ID: {task_id}")

            if task_id is None:
                logger.error(f"[{APP_NAME}] Failed to add task to queue for {request_type.upper()}: {string}")
                raise HTTPException(status_code=500, detail="Failed to add task to queue")

            logger.info(f"[{APP_NAME}] {request_type.upper()} task {task_id} queued for string: {string}")
            return {
                "task_id": task_id,
                "status": "queued",
                "message": f"{request_type.upper()} calculation queued"
            }
    except Exception as e:
        logger.error(f"[{APP_NAME}] Unexpected error in add_task: {e}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")


def process_request(request_type: str, string: str) -> Union[Dict[str, Any], JSONResponse]:
    """Generic function to process hash requests"""
    logger.info(f"[{APP_NAME}] Received {request_type.upper()} request for string: {string}")

    # Check cache first
    logger.info(f"[{APP_NAME}] Checking cache for {request_type.upper()}: {string}")
    try:
        cached_result = check_cache(request_type, string)
        if cached_result:
            logger.info(f"[{APP_NAME}] Cache hit, returning cached result")
            return cached_result
        else:
            logger.info(f"[{APP_NAME}] Cache miss, adding task to queue")
            # Add task to queue
            return add_task(request_type, string)
    except Exception as e:
        logger.error(f"[{APP_NAME}] Error checking cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache error: {e}")




# Hash endpoints using the generic function
@app.post("/hash/sha256")
def convert_str_to_sha256(input: InputString):
    return process_request("sha256", input.string)


@app.post("/hash/md5")
def convert_str_to_md5(input: InputString):
    return process_request("md5", input.string)


@app.post("/hash/argon2")
def convert_str_to_argon2(input: InputString):
    return process_request("argon2", input.string)


def execute_safe_query(db_manager: DatabaseManager, query: str, params: Tuple, task_id: int):
    """Execute a database query safely with error handling"""
    if not db_manager.cursor:
        logger.error(f"[{APP_NAME}] Database cursor lost during query for task {task_id}")
        raise HTTPException(status_code=500, detail="Database connection lost")

    try:
        db_manager.cursor.execute(query, params)
        return db_manager.cursor.fetchone()
    except Exception as e:
        logger.error(f"[{APP_NAME}] Database query error for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")


def parse_task_result(result: Any) -> Union[Dict[str, Any], str, None]:
    """Parse task result from database"""
    if not result:
        return None

    if isinstance(result, str):
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return result
    else:
        # Result might already be a dict from psycopg
        return result


@app.get("/task/{task_id}")
def get_task_status(task_id: int):
    """Get the status of a specific task"""
    logger.info(f"[{APP_NAME}] Received request to get task status for ID: {task_id}")

    with get_database_connection() as db:
        # Query the task status
        task = execute_safe_query(
            db,
            """
            SELECT id, task_type, status, result, error, created_at, started_at, completed_at
            FROM tasks
            WHERE id = %s
            """,
            (task_id,),
            task_id
        )

        if task is None:
            logger.warning(f"[{APP_NAME}] Task with ID {task_id} not found")
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

        task_id, task_type, status, result, error, created_at, started_at, completed_at = task
        logger.info(f"[{APP_NAME}] Retrieved task {task_id} with status: {status}")

        # Parse the result
        parsed_result = parse_task_result(result)

        # Cache the result if completed successfully
        if status == 'completed' and parsed_result and isinstance(parsed_result, dict):
            cache_result(task_type, parsed_result)

        # Return task information
        logger.info(f"[{APP_NAME}] Returning task {task_id} info: {status}")
        return {
            "id": task_id,
            "type": task_type,
            "status": status,
            "result": parsed_result,
            "error": error,
            "created_at": created_at,
            "started_at": started_at,
            "completed_at": completed_at
        }


@app.get("/health")
def health_check():
    """Health check endpoint for load balancer"""
    logger.info(f"[{APP_NAME}] Received health check request")
    return {"status": "healthy", "service": "hash-api"}


@app.get("/cache/stats")
def cache_stats():
    """Get cache statistics"""
    logger.info(f"[{APP_NAME}] Received request to get cache stats")
    return shared_cache.get_stats()


@app.post("/cache/clear")
def clear_cache():
    """Clear all cache entries"""
    logger.info(f"[{APP_NAME}] Received request to clear cache")
    shared_cache.clear()
    logger.info(f"[{APP_NAME}] Cache cleared successfully")
    return {"message": "Cache cleared successfully"}
