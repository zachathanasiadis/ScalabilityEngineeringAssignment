#!/usr/bin/env python3
from db.db_manager import DatabaseManager
from queue_service.queue_manager import TaskQueue
from worker.worker import Worker
from tasks.fibonacci import fibonacci_task
from tasks.hash_tasks import md5_task, sha256_task

def run_worker():
    """Initialize and run a worker process"""
    # Setup database connection
    db_manager = DatabaseManager()
    db_manager.connect()

    # Create tables if they don't exist
    db_manager.create_tables()

    # Initialize queue manager
    task_queue = TaskQueue(db_manager)

    # Create worker with 2 second polling interval
    worker = Worker(task_queue, db_manager, polling_interval=2)

    # Register task handlers
    worker.register_task_handler('fibonacci', fibonacci_task)
    worker.register_task_handler('md5', md5_task)
    worker.register_task_handler('sha256', sha256_task)

    print("Starting worker. Press Ctrl+C to stop.")
    worker.start()

if __name__ == "__main__":
    run_worker()