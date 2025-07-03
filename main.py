from fastapi import FastAPI, BackgroundTasks, HTTPException
from pydantic import BaseModel
import hashlib
from queue_service.queue_manager import TaskQueue
from db.db_manager import DatabaseManager
import json

app = FastAPI()

# Initialize task queue
db_manager = DatabaseManager()
task_queue = TaskQueue(db_manager)
task_queue.initialize()

str_to_hash256_mappings = {}
str_to_md5_mappings = {}

class InputString(BaseModel):
    string: str


@app.post("/hash/sha256")
def convert_str_to_sha256(input: InputString):
    string = input.string

    # Add task to queue
    task_id = task_queue.add_task('sha256', {'string': string})

    if task_id is None:
        raise HTTPException(status_code=500, detail="Failed to add task to queue")

    return {"task_id": task_id, "status": "queued", "message": "SHA256 hash calculation queued"}


@app.post("/hash/md5")
def convert_str_to_md5(input: InputString):
    string = input.string

    # Add task to queue
    task_id = task_queue.add_task('md5', {'string': string})

    if task_id is None:
        raise HTTPException(status_code=500, detail="Failed to add task to queue")

    return {"task_id": task_id, "status": "queued", "message": "MD5 hash calculation queued"}


@app.get("/hashes")
def get_hashes():
    return {"SHA256": str_to_hash256_mappings, "MD5": str_to_md5_mappings}


@app.get("/task/{task_id}")
def get_task_status(task_id: int):
    """Get the status of a specific task"""
    # Connect to the database
    db_manager.connect()

    try:
        # Query the task status
        db_manager.cursor.execute(
            """
            SELECT id, task_type, status, result, error, created_at, started_at, completed_at
            FROM tasks
            WHERE id = %s
            """,
            (task_id,)
        )
        task = db_manager.cursor.fetchone()

        if task is None:
            raise HTTPException(status_code=404, detail=f"Task with ID {task_id} not found")

        task_id, task_type, status, result, error, created_at, started_at, completed_at = task

        # Parse the JSON result if available
        if result and isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                pass

        # Add the hash to our mappings if completed successfully
        if status == 'completed' and result:
            if task_type == 'md5' and 'md5_hash' in result and 'original_string' in result:
                str_to_md5_mappings[result['original_string']] = result['md5_hash']
            elif task_type == 'sha256' and 'sha256_hash' in result and 'original_string' in result:
                str_to_hash256_mappings[result['original_string']] = result['sha256_hash']

        # Return task information
        return {
            "id": task_id,
            "type": task_type,
            "status": status,
            "result": result,
            "error": error,
            "created_at": created_at,
            "started_at": started_at,
            "completed_at": completed_at
        }

    finally:
        db_manager.close()
