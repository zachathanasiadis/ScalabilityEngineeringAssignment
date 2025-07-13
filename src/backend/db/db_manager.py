import os
import psycopg
from dotenv import load_dotenv
from .connection_limiter import create_limited_connection

load_dotenv()

class DatabaseManager:
    def __init__(self, db_name=None, db_user=None, db_password=None, db_host=None, db_port=None):
        self.db_name = db_name or os.getenv("DB_NAME", "")
        self.db_user = db_user or os.getenv("DB_USER", "")
        self.db_password = db_password or os.getenv("DB_PASSWORD", "")
        self.db_host = db_host or os.getenv("DB_HOST", "")
        self.db_port = db_port or os.getenv("DB_PORT", "")
        self.connection = None
        self.cursor = None

    def connect(self):
        """Connect to the PostgreSQL database server with connection limiting"""
        result = create_limited_connection(
            self.db_name,
            self.db_user,
            self.db_password,
            self.db_host,
            self.db_port
        )

        if result["success"]:
            self.connection = result["connection"]
            self.cursor = self.connection.cursor()
            return {"success": True, "error": None}
        else:
            self.connection = None
            self.cursor = None
            return {
                "success": False,
                "error": result["error"],
                "details": {
                    "db_name": self.db_name,
                    "db_user": self.db_user,
                    "db_host": self.db_host,
                    "db_port": self.db_port,
                    **result.get("details", {})
                }
            }

    def close(self):
        """Close the database connection"""
        if self.connection:
            if self.cursor:
                self.cursor.close()
            self.connection.close()
            print("Database connection closed.")
        self.connection = None
        self.cursor = None

    def create_tables(self):
        """Create necessary tables if they don't exist"""
        if not self.connection or not self.cursor:
            print("Not connected to database. Call connect() first.")
            return False

        try:
            # Tasks table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id SERIAL PRIMARY KEY,
                    task_type VARCHAR(50) NOT NULL,
                    parameters JSONB,
                    status VARCHAR(20) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    result JSONB,
                    error TEXT
                );
            ''')

            # Workers table
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS workers (
                    id SERIAL PRIMARY KEY,
                    worker_id VARCHAR(50) NOT NULL UNIQUE,
                    status VARCHAR(20) DEFAULT 'idle',
                    last_heartbeat TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    current_task_id INTEGER REFERENCES tasks(id)
                );
            ''')

            self.connection.commit()
            print("Tables created successfully.")
            return True
        except Exception as error:
            print(f"Error while creating tables: {error}")
            if self.connection:
                self.connection.rollback()
            return False

    def add_task(self, task_type, parameters=None):
        """Add a new task to the queue"""
        if not self.connection or not self.cursor:
            print("Not connected to database. Call connect() first.")
            return None

        try:
            self.cursor.execute(
                """
                INSERT INTO tasks (task_type, parameters)
                VALUES (%s, %s)
                RETURNING id
                """,
                (task_type, parameters)
            )
            result = self.cursor.fetchone()
            if not result:
                return None

            task_id = result[0]
            self.connection.commit()
            print(f"Task added with ID: {task_id}")
            return task_id
        except Exception as error:
            print(f"Error while adding task: {error}")
            if self.connection:
                self.connection.rollback()
            return None

    def get_next_task(self):
        """Get the next pending task from the queue"""
        if not self.connection or not self.cursor:
            print("Not connected to database. Call connect() first.")
            return None

        try:
            self.cursor.execute(
                """
                SELECT id, task_type, parameters
                FROM tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
                """
            )
            task = self.cursor.fetchone()
            if task:
                task_id, task_type, parameters = task
                self.cursor.execute(
                    """
                    UPDATE tasks
                    SET status = 'processing', started_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (task_id,)
                )
                self.connection.commit()
                return {"id": task_id, "task_type": task_type, "parameters": parameters}
            return None
        except Exception as error:
            print(f"Error while getting next task: {error}")
            if self.connection:
                self.connection.rollback()
            return None

    def complete_task(self, task_id, result=None, error=None):
        """Mark a task as completed or failed"""
        if not self.connection or not self.cursor:
            print("Not connected to database. Call connect() first.")
            return False

        try:
            status = 'completed' if error is None else 'failed'
            self.cursor.execute(
                """
                UPDATE tasks
                SET status = %s, completed_at = CURRENT_TIMESTAMP, result = %s, error = %s
                WHERE id = %s
                """,
                (status, result, error, task_id)
            )
            self.connection.commit()
            print(f"Task {task_id} marked as {status}")
            return True
        except Exception as error:
            print(f"Error while completing task: {error}")
            if self.connection:
                self.connection.rollback()
            return False

    def register_worker(self, worker_id):
        """Register a new worker or update existing worker"""
        if not self.connection or not self.cursor:
            print("Not connected to database. Call connect() first.")
            return None

        try:
            self.cursor.execute(
                """
                INSERT INTO workers (worker_id, status, last_heartbeat)
                VALUES (%s, 'idle', CURRENT_TIMESTAMP)
                ON CONFLICT (worker_id)
                DO UPDATE SET status = 'idle', last_heartbeat = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (worker_id,)
            )
            result = self.cursor.fetchone()
            if not result:
                return None

            worker_db_id = result[0]
            self.connection.commit()
            print(f"Worker {worker_id} registered with ID: {worker_db_id}")
            return worker_db_id
        except Exception as error:
            print(f"Error while registering worker: {error}")
            if self.connection:
                self.connection.rollback()
            return None

    def update_worker_status(self, worker_id, status, task_id=None):
        """Update worker status and current task"""
        if not self.connection or not self.cursor:
            print("Not connected to database. Call connect() first.")
            return False

        try:
            self.cursor.execute(
                """
                UPDATE workers
                SET status = %s, last_heartbeat = CURRENT_TIMESTAMP, current_task_id = %s
                WHERE worker_id = %s
                """,
                (status, task_id, worker_id)
            )
            self.connection.commit()
            return True
        except Exception as error:
            print(f"Error while updating worker status: {error}")
            if self.connection:
                self.connection.rollback()
            return False