import json
import time
import uuid
from db.db_manager import DatabaseManager
from queue_service.queue_manager import TaskQueue

class Worker:
    def __init__(self, task_queue=None, db_manager=None, polling_interval=5):
        """Initialize a worker to process tasks from the queue

        Args:
            task_queue (TaskQueue): Task queue manager
            db_manager (DatabaseManager): Database manager
            polling_interval (int): Time between checking for new tasks in seconds
        """
        self.worker_id = f"worker-{uuid.uuid4()}"
        self.db_manager = db_manager or DatabaseManager()
        self.task_queue = task_queue or TaskQueue(self.db_manager)
        self.polling_interval = polling_interval
        self.running = False
        self.task_handlers = {}

    def register_task_handler(self, task_type, handler_function):
        """Register a function to handle a specific task type

        Args:
            task_type (str): Type of task to handle
            handler_function (callable): Function to process the task
        """
        self.task_handlers[task_type] = handler_function

    def connect(self):
        """Connect to the database and initialize the worker"""
        self.db_manager.connect()
        self.db_manager.register_worker(self.worker_id)

    def close(self):
        """Close database connection and clean up"""
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()

    def start(self):
        """Start the worker to process tasks"""
        self.running = True
        self.connect()

        print(f"Worker {self.worker_id} started.")

        try:
            while self.running:
                task = self.task_queue.get_next_task()
                if task:
                    try:
                        task_id = task['id']
                        task_type = task['task_type']
                        parameters = task['parameters']

                        print(f"Processing task {task_id} of type {task_type}")
                        self.db_manager.update_worker_status(self.worker_id, 'busy', task_id)

                        # Parse the task parameters if they're a JSON string
                        if parameters and isinstance(parameters, str):
                            try:
                                parameters = json.loads(parameters)
                            except json.JSONDecodeError:
                                pass

                        # Execute the task
                        if task_type in self.task_handlers:
                            result = self.task_handlers[task_type](parameters)
                            self.task_queue.complete_task(task_id, result)
                            print(f"Task {task_id} completed successfully")
                        else:
                            error = f"No handler registered for task type: {task_type}"
                            self.task_queue.complete_task(task_id, None, error)
                            print(f"Task {task_id} failed: {error}")

                    except Exception as e:
                        print(f"Error processing task {task.get('id', 'unknown')}: {str(e)}")
                        self.task_queue.complete_task(task.get('id'), None, str(e))
                    finally:
                        self.db_manager.update_worker_status(self.worker_id, 'idle')

                else:
                    # No task found, wait before checking again
                    time.sleep(self.polling_interval)

        except KeyboardInterrupt:
            print("Worker stopping due to keyboard interrupt...")
        except Exception as e:
            print(f"Worker encountered an error: {str(e)}")
        finally:
            self.stop()

    def stop(self):
        """Stop the worker"""
        self.running = False
        print(f"Worker {self.worker_id} stopping...")
        self.close()
        print(f"Worker {self.worker_id} stopped.")

    def __enter__(self):
        """Support for context manager protocol"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager protocol"""
        self.close()