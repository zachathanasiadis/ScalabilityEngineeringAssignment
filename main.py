from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import hashlib
import os
import time
import logging
from datetime import datetime
from queue_service.queue_manager import TaskQueue
from db.db_manager import DatabaseManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
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
    from cache.shared_cache import shared_cache
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
if connection_result["success"]:
    logger.info(f"[{APP_NAME}] Database connection successful, creating tables")
    db_manager.create_tables()
    db_manager.close()
    logger.info(f"[{APP_NAME}] Database tables created successfully")
else:
    logger.error(f"[{APP_NAME}] Failed to connect to database at startup: {connection_result['error']}")
    logger.error(f"[{APP_NAME}] Connection details: {connection_result['details']}")
    logger.error(f"[{APP_NAME}] Failed to connect to database during startup. Please check your database configuration.")

logger.info(f"[{APP_NAME}] Application initialization complete")

class InputString(BaseModel):
    string: str


@app.post("/hash/sha256")
def convert_str_to_sha256(input: InputString):
    string = input.string
    logger.info(f"[{APP_NAME}] Received SHA256 request for string: {string}")

    # Check cache first
    cache_key = f"sha256:{string}"
    cached_result = shared_cache.get(cache_key)

    if cached_result:
        logger.info(f"[{APP_NAME}] SHA256 result found in cache for string: {string}")
        return {"result": cached_result, "source": "cache"}

    # Establish a new connection for this request
    connection_result = db_manager.connect()
    if not connection_result["success"]:
        error_details = connection_result["details"]
        logger.error(f"[{APP_NAME}] Database connection failed for SHA256: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'"
        )

    try:
        # Add task to queue
        task_id = task_queue.add_task('sha256', {'string': string})

        if task_id is None:
            logger.error(f"[{APP_NAME}] Failed to add task to queue for SHA256: {string}")
            raise HTTPException(status_code=500, detail="Failed to add task to queue")

        logger.info(f"[{APP_NAME}] SHA256 task {task_id} queued for string: {string}")
        return {"task_id": task_id, "status": "queued", "message": "SHA256 hash calculation queued"}
    finally:
        # Always close the connection
        db_manager.close()


@app.post("/hash/md5")
def convert_str_to_md5(input: InputString):
    string = input.string
    logger.info(f"[{APP_NAME}] Received MD5 request for string: {string}")

    # Check cache first
    cache_key = f"md5:{string}"
    cached_result = shared_cache.get(cache_key)

    if cached_result:
        logger.info(f"[{APP_NAME}] MD5 result found in cache for string: {string}")
        return {"result": cached_result, "source": "cache"}

    # Establish a new connection for this request
    connection_result = db_manager.connect()
    if not connection_result["success"]:
        error_details = connection_result["details"]
        logger.error(f"[{APP_NAME}] Database connection failed for MD5: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'"
        )

    try:
        # Add task to queue
        task_id = task_queue.add_task('md5', {'string': string})

        if task_id is None:
            logger.error(f"[{APP_NAME}] Failed to add task to queue for MD5: {string}")
            raise HTTPException(status_code=500, detail="Failed to add task to queue")

        logger.info(f"[{APP_NAME}] MD5 task {task_id} queued for string: {string}")
        return {"task_id": task_id, "status": "queued", "message": "MD5 hash calculation queued"}
    finally:
        # Always close the connection
        db_manager.close()

@app.post("/hash/argon2")
def convert_str_to_argon2(input: InputString):
    string = input.string
    logger.info(f"[{APP_NAME}] Received argon2 request for string: {string}")

    # Check cache first
    cache_key = f"argon2:{string}"
    cached_result = shared_cache.get(cache_key)

    if cached_result:
        logger.info(f"[{APP_NAME}] argon2 result found in cache for string: {string}")
        return {"result": cached_result, "source": "cache"}

    # Establish a new connection for this request
    connection_result = db_manager.connect()
    if not connection_result["success"]:
        error_details = connection_result["details"]
        logger.error(f"[{APP_NAME}] Database connection failed for argon2: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'"
        )

    try:
        # Add task to queue
        task_id = task_queue.add_task('argon2', {'string': string})

        if task_id is None:
            logger.error(f"[{APP_NAME}] Failed to add task to queue for argon2: {string}")
            raise HTTPException(status_code=500, detail="Failed to add task to queue")

        logger.info(f"[{APP_NAME}] argon2 task {task_id} queued for string: {string}")
        return {"task_id": task_id, "status": "queued", "message": "argon2 hash calculation queued"}
    finally:
        # Always close the connection
        db_manager.close()


@app.get("/hashes")
def get_hashes():
    """Get all computed hashes from database and cache"""
    logger.info(f"[{APP_NAME}] Received request to get all hashes")
    # Connect to the database
    connection_result = db_manager.connect()
    if not connection_result["success"]:
        error_details = connection_result["details"]
        logger.error(f"[{APP_NAME}] Database connection failed for get_hashes: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'"
        )

    try:
        # Query completed tasks from database
        db_manager.cursor.execute("""
            SELECT task_type, result
            FROM tasks
            WHERE status = 'completed' AND result IS NOT NULL
        """)

        completed_tasks = db_manager.cursor.fetchall()
        logger.info(f"[{APP_NAME}] Retrieved {len(completed_tasks)} completed tasks from database")

        sha256_hashes = {}
        md5_hashes = {}

        for task_type, result in completed_tasks:
            if isinstance(result, str):
                try:
                    parsed_result = json.loads(result)
                except json.JSONDecodeError:
                    logger.warning(f"[{APP_NAME}] Skipping task with invalid JSON result: {result}")
                    continue
            else:
                parsed_result = result

            if isinstance(parsed_result, dict):
                if task_type == 'sha256' and 'sha256_hash' in parsed_result and 'original_string' in parsed_result:
                    sha256_hashes[parsed_result['original_string']] = parsed_result['sha256_hash']
                    logger.info(f"[{APP_NAME}] Added SHA256 hash to result: {parsed_result['original_string']}")
                elif task_type == 'md5' and 'md5_hash' in parsed_result and 'original_string' in parsed_result:
                    md5_hashes[parsed_result['original_string']] = parsed_result['md5_hash']
                    logger.info(f"[{APP_NAME}] Added MD5 hash to result: {parsed_result['original_string']}")

        logger.info(f"[{APP_NAME}] Returning {len(sha256_hashes)} SHA256 and {len(md5_hashes)} MD5 hashes")
        return {
            "SHA256": sha256_hashes,
            "MD5": md5_hashes,
            "cache_stats": shared_cache.get_stats()
        }
    finally:
        db_manager.close()


@app.get("/task/{task_id}")
def get_task_status(task_id: int):
    """Get the status of a specific task"""
    logger.info(f"[{APP_NAME}] Received request to get task status for ID: {task_id}")
    # Connect to the database
    connection_result = db_manager.connect()
    if not connection_result["success"]:
        error_details = connection_result["details"]
        logger.error(f"[{APP_NAME}] Database connection failed for get_task_status: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'")
        raise HTTPException(
            status_code=500,
            detail=f"Database connection failed: {connection_result['error']}. "
                   f"Trying to connect to {error_details['db_name']}@{error_details['db_host']}:{error_details['db_port']} "
                   f"as user '{error_details['db_user']}'"
        )

    try:
        # Define a helper function for safe database query
        def execute_query(query, params):
            if not db_manager.cursor:
                logger.error(f"[{APP_NAME}] Database cursor lost during task status query for task {task_id}")
                raise HTTPException(status_code=500, detail="Database connection lost")
            try:
                db_manager.cursor.execute(query, params)
                return db_manager.cursor.fetchone()
            except Exception as e:
                logger.error(f"[{APP_NAME}] Database query error for task {task_id}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Database query error: {str(e)}")

        # Query the task status using the helper
        task = execute_query(
            """
            SELECT id, task_type, status, result, error, created_at, started_at, completed_at
            FROM tasks
            WHERE id = %s
            """,
            (task_id,)
        )

        if task is None:
            logger.warning(f"[{APP_NAME}] Task with ID {task_id} not found")
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

        task_id, task_type, status, result, error, created_at, started_at, completed_at = task
        logger.info(f"[{APP_NAME}] Retrieved task {task_id} with status: {status}")

        # Parse the JSON result if available
        parsed_result = None
        if result:
            if isinstance(result, str):
                try:
                    parsed_result = json.loads(result)
                except json.JSONDecodeError:
                    parsed_result = result
            else:
                # Result might already be a dict from psycopg
                parsed_result = result

        # Cache the result if completed successfully
        if status == 'completed' and parsed_result and isinstance(parsed_result, dict):
            if task_type == 'md5' and 'md5_hash' in parsed_result and 'original_string' in parsed_result:
                cache_key = f"md5:{parsed_result['original_string']}"
                shared_cache.set(cache_key, parsed_result, ttl=3600)  # Cache for 1 hour
                logger.info(f"[{APP_NAME}] Cached MD5 hash for string: {parsed_result['original_string']}")
            elif task_type == 'sha256' and 'sha256_hash' in parsed_result and 'original_string' in parsed_result:
                cache_key = f"sha256:{parsed_result['original_string']}"
                shared_cache.set(cache_key, parsed_result, ttl=3600)  # Cache for 1 hour
                logger.info(f"[{APP_NAME}] Cached SHA256 hash for string: {parsed_result['original_string']}")

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

    finally:
        db_manager.close()


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
