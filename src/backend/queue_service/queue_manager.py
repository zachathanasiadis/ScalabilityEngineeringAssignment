import json
from db.db_manager import DatabaseManager
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("worker.log")
    ]
)
logger = logging.getLogger(__name__)
class TaskQueue:
    def __init__(self, db_manager=None):
        """Initialize the TaskQueue with a database manager"""
        self.db_manager = db_manager or DatabaseManager()

    def connect(self):
        """Connect to the database"""
        if not self.db_manager.connect()["error"]:
            return True
        else:
            return False

    def close(self):
        """Close database connection"""
        self.db_manager.close()

    def initialize(self):
        """Initialize the queue and ensure required tables exist"""
        if self.connect():
            result = self.db_manager.create_tables()
            self.close()
            return result
        return False

    def add_task(self, task_type, parameters=None):
        """Add a task to the queue

        Args:
            task_type (str): Type of task (e.g., 'fibonacci')
            parameters (dict): Parameters needed for the task

        Returns:
            int: ID of the created task
        """
        logger.info(f"[QueueManager] Adding task to queue: {task_type} with parameters: {parameters}")
        if parameters and not isinstance(parameters, str):
            parameters = json.dumps(parameters)

        # The db_manager now handles connection internally
        return self.db_manager.add_task(task_type, parameters)

    def get_next_task(self):
        """Get the next task from the queue

        Returns:
            dict: Task information including id, task_type, and parameters
        """
        return self.db_manager.get_next_task()

    def complete_task(self, task_id, result=None, error=None):
        """Mark a task as completed or failed

        Args:
            task_id (int): ID of the task
            result: The result of the task execution
            error (str): Error message if the task failed

        Returns:
            bool: Success status
        """
        if result and not isinstance(result, str):
            result = json.dumps(result)

        return self.db_manager.complete_task(task_id, result, error)