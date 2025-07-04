from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import hashlib
from queue_service.queue_manager import TaskQueue
from db.db_manager import DatabaseManager
import json

app = FastAPI()

# Initialize these only once
db_manager = DatabaseManager()
task_queue = TaskQueue(db_manager)

# Create tables if they don't exist
if db_manager.connect():
    db_manager.create_tables()
    db_manager.close()
else:
    print("Failed to connect to database during startup. Please check your database configuration.")

str_to_hash256_mappings = {}
str_to_md5_mappings = {}

class InputString(BaseModel):
    string: str


@app.post("/hash/sha256")
def convert_str_to_sha256(input: InputString):
    string = input.string

    # Establish a new connection for this request
    if not db_manager.connect():
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Add task to queue
        task_id = task_queue.add_task('sha256', {'string': string})

        if task_id is None:
            raise HTTPException(status_code=500, detail="Failed to add task to queue")

        return {"task_id": task_id, "status": "queued", "message": "SHA256 hash calculation queued"}
    finally:
        # Always close the connection
        db_manager.close()


@app.post("/hash/md5")
def convert_str_to_md5(input: InputString):
    string = input.string

    # Establish a new connection for this request
    if not db_manager.connect():
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Add task to queue
        task_id = task_queue.add_task('md5', {'string': string})

        if task_id is None:
            raise HTTPException(status_code=500, detail="Failed to add task to queue")

        return {"task_id": task_id, "status": "queued", "message": "MD5 hash calculation queued"}
    finally:
        # Always close the connection
        db_manager.close()


@app.get("/hashes")
def get_hashes():
    return {"SHA256": str_to_hash256_mappings, "MD5": str_to_md5_mappings}


@app.get("/task/{task_id}")
def get_task_status(task_id: int):
    """Get the status of a specific task"""
    # Connect to the database
    if not db_manager.connect():
        raise HTTPException(status_code=500, detail="Database connection failed")

    try:
        # Define a helper function for safe database query
        def execute_query(query, params):
            if not db_manager.cursor:
                raise HTTPException(status_code=500, detail="Database connection lost")
            try:
                db_manager.cursor.execute(query, params)
                return db_manager.cursor.fetchone()
            except Exception as e:
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
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

        task_id, task_type, status, result, error, created_at, started_at, completed_at = task

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

        # Add the hash to our mappings if completed successfully
        if status == 'completed' and parsed_result:
            if task_type == 'md5' and isinstance(parsed_result, dict):
                if 'md5_hash' in parsed_result and 'original_string' in parsed_result:
                    str_to_md5_mappings[parsed_result['original_string']] = parsed_result['md5_hash']
            elif task_type == 'sha256' and isinstance(parsed_result, dict):
                if 'sha256_hash' in parsed_result and 'original_string' in parsed_result:
                    str_to_hash256_mappings[parsed_result['original_string']] = parsed_result['sha256_hash']

        # Return task information
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
