import json
import time
import uuid
import os
import logging
from db.db_manager import DatabaseManager
from queue_service.queue_manager import TaskQueue

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("worker.log")
    ]
)
logger = logging.getLogger(__name__)

class Worker:
    def __init__(self, task_queue=None, db_manager=None, polling_interval=5):
        """Initialize a worker to process tasks from the queue

        Args:
            task_queue (TaskQueue): Task queue manager
            db_manager (DatabaseManager): Database manager
            polling_interval (int): Time between checking for new tasks in seconds
        """
        self.worker_id = f"worker-{uuid.uuid4()}"
        self.worker_name = os.getenv("WORKER_NAME", self.worker_id)
        logger.info(f"=== Initializing {self.worker_name} ({self.worker_id}) ===")

        self.db_manager = db_manager or DatabaseManager()
        self.task_queue = task_queue or TaskQueue(self.db_manager)
        self.polling_interval = polling_interval
        self.running = False
        self.task_handlers = {}
        self.tasks_processed = 0

        logger.info(f"[{self.worker_name}] Worker initialized with polling interval: {polling_interval}s")

    def register_task_handler(self, task_type, handler_function):
        """Register a function to handle a specific task type

        Args:
            task_type (str): Type of task to handle
            handler_function (callable): Function to process the task
        """
        self.task_handlers[task_type] = handler_function
        logger.info(f"[{self.worker_name}] Registered handler for task type: {task_type}")

    def connect(self):
        """Connect to the database and initialize the worker"""
        logger.info(f"[{self.worker_name}] Connecting to database...")
        connection_result = self.db_manager.connect()
        if connection_result["success"]:
            self.db_manager.register_worker(self.worker_id)
            logger.info(f"[{self.worker_name}] Successfully connected to database and registered worker")
        else:
            logger.error(f"[{self.worker_name}] Failed to connect to database: {connection_result['error']}")
            raise Exception(f"Database connection failed: {connection_result['error']}")

    def close(self):
        """Close database connection and clean up"""
        logger.info(f"[{self.worker_name}] Closing database connection...")
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close()
        logger.info(f"[{self.worker_name}] Worker shutdown complete")

    def start(self):
        """Start the worker to process tasks"""
        self.running = True
        self.connect()

        logger.info(f"[{self.worker_name}] Worker started and ready to process tasks")

        try:
            while self.running:
                try:
                    # Get next task from queue
                    #logger.debug(f"[{self.worker_name}] Checking for new tasks...")
                    task = self.task_queue.get_next_task()

                    if task:
                        task_id = task["id"]
                        task_type = task["task_type"]
                        parameters = task["parameters"]
                        logger.info(f"[{self.worker_name}] *** PICKED UP TASK {task_id} (type: {task_type}) ***")

                        # Check if we have a handler for this task type
                        if task_type in self.task_handlers:
                            try:
                                # Parse parameters if it's a JSON string
                                if isinstance(parameters, str):
                                    parameters = json.loads(parameters)

                                logger.info(f"[{self.worker_name}] Processing task {task_id} with parameters: {parameters}")

                                # Call the handler function
                                result = self.task_handlers[task_type](parameters)

                                # Complete the task
                                self.task_queue.complete_task(task_id, result)
                                self.tasks_processed += 1

                                logger.info(f"[{self.worker_name}] *** COMPLETED TASK {task_id} *** (Total processed: {self.tasks_processed})")

                            except Exception as e:
                                error_msg = f"Error processing task {task_id}: {str(e)}"
                                logger.error(f"[{self.worker_name}] {error_msg}")
                                self.task_queue.complete_task(task_id, None, error_msg)
                        else:
                            error_msg = f"No handler registered for task type '{task_type}'"
                            logger.error(f"[{self.worker_name}] {error_msg}")
                            self.task_queue.complete_task(task_id, None, error_msg)
                    else:
                       #logger.debug(f"[{self.worker_name}] No tasks available, waiting {self.polling_interval}s...")
                        time.sleep(self.polling_interval)

                except Exception as e:
                    logger.error(f"[{self.worker_name}] Error in worker loop: {str(e)}")
                    time.sleep(self.polling_interval)

        except KeyboardInterrupt:
            logger.info(f"[{self.worker_name}] Received interrupt signal, stopping...")
        finally:
            self.close()

    def stop(self):
        """Stop the worker"""
        logger.info(f"[{self.worker_name}] Stop signal received")
        self.running = False