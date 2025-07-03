import time
import sys
import signal
import threading
from db.db_manager import DatabaseManager
from queue_service.queue_manager import TaskQueue
from worker.worker import Worker
from tasks.fibonacci import fibonacci_task

def setup_database():
    """Setup the database and tables"""
    db_manager = DatabaseManager()
    db_manager.connect()
    db_manager.create_tables()
    db_manager.close()
    print("Database setup complete.")

def start_worker(worker_id, stop_event):
    """Start a worker in a separate thread"""
    print(f"Starting worker {worker_id}...")
    db_manager = DatabaseManager()
    task_queue = TaskQueue(db_manager)
    worker = Worker(task_queue, db_manager)

    # Register task handlers
    worker.register_task_handler('fibonacci', fibonacci_task)

    # Start the worker
    worker.connect()

    try:
        while not stop_event.is_set():
            task = worker.task_queue.get_next_task()
            if task:
                try:
                    worker.db_manager.update_worker_status(worker.worker_id, 'busy', task['id'])

                    # Process the task
                    task_id = task['id']
                    task_type = task['task_type']
                    parameters = task['parameters']

                    print(f"[Worker {worker_id}] Processing task {task_id} of type {task_type}")

                    # Execute the task
                    if task_type in worker.task_handlers:
                        result = worker.task_handlers[task_type](parameters)
                        worker.task_queue.complete_task(task_id, result)
                        print(f"[Worker {worker_id}] Task {task_id} completed with result: {result}")
                    else:
                        error = f"No handler registered for task type: {task_type}"
                        worker.task_queue.complete_task(task_id, None, error)
                        print(f"[Worker {worker_id}] Task {task_id} failed: {error}")

                except Exception as e:
                    print(f"[Worker {worker_id}] Error processing task: {str(e)}")
                finally:
                    worker.db_manager.update_worker_status(worker.worker_id, 'idle')
            else:
                # No task found, wait before checking again
                time.sleep(worker.polling_interval)
    except Exception as e:
        print(f"[Worker {worker_id}] Encountered an error: {str(e)}")
    finally:
        print(f"[Worker {worker_id}] Shutting down...")
        worker.close()

def add_sample_tasks(num_tasks):
    """Add sample Fibonacci tasks to the queue"""
    task_queue = TaskQueue()
    task_queue.connect()

    try:
        for i in range(num_tasks):
            # Vary the Fibonacci position a bit for demonstration
            position = 120 + (i % 10)
            parameters = {'n': position}
            task_id = task_queue.add_task('fibonacci', parameters)
            print(f"Added Fibonacci task {task_id} for position {position}")
    finally:
        task_queue.close()

def demo():
    """Run a demonstration of the task queue system"""
    # Setup the database first
    setup_database()

    # Add some sample tasks
    print("Adding sample tasks to the queue...")
    add_sample_tasks(10)

    # Start multiple workers
    print("Starting workers...")
    stop_event = threading.Event()
    workers = []
    num_workers = 3

    for i in range(num_workers):
        worker_thread = threading.Thread(
            target=start_worker,
            args=(i + 1, stop_event),
            daemon=True
        )
        workers.append(worker_thread)
        worker_thread.start()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down workers...")
        stop_event.set()
        for worker_thread in workers:
            if worker_thread.is_alive():
                worker_thread.join(timeout=2)
        print("All workers stopped.")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Keep the main thread alive
    try:
        while True:
            alive_workers = sum(1 for w in workers if w.is_alive())
            print(f"Active workers: {alive_workers}/{num_workers}")

            if alive_workers == 0:
                print("All workers have stopped. Exiting.")
                break

            time.sleep(5)
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--add-tasks":
        # Just add tasks without starting workers
        num_tasks = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        setup_database()
        add_sample_tasks(num_tasks)
    else:
        # Run the full demo
        demo()