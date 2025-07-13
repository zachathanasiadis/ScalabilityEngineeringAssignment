# Scalability Engineering Prototype Assignment

This project is a scalable, containerized task processing system built with FastAPI, PostgreSQL, and Docker. It features a load balancer, multiple backend API instances, worker processes, and a shared cache using the database.

The main focus of the system is to handle computational tasks in a scalable and asynchronous manner. Users can submit tasks to done via API endpoints; these requests are queued in the database and processed by worker services. Results are cached for fast retrieval and to avoid redundant computations. The architecture ensures efficient resource usage and high throughput with option to scale-out.

## Features

- **Load Balancer**: Distributes requests to backend API instances using round-robin or least-connections strategies ([src/loadbalancer/loadbalancer.py](src/loadbalancer/loadbalancer.py)).`
- **Backend API**: Provides endpoints for task calculations ([src/backend/main.py](src/backend/main.py)).
- **Task Queue**: Tasks are queued in the database and processed asynchronously by workers ([src/backend/queue_service/queue_manager.py](src/backend/queue_service/queue_manager.py)).
- **Workers**: Poll the queue and process tasks ([src/backend/worker/worker.py](src/backend/worker/worker.py), [src/run_worker.py](src/run_worker.py)).
- **Shared Cache**: Results are cached in the database for fast retrieval ([src/backend/db/shared_cache.py](src/backend/db/shared_cache.py)).
- **PostgreSQL Database**: Stores tasks, workers, and cache entries ([src/backend/db/db_manager.py](src/backend/db/db_manager.py), [src/backend/db/init.sql](src/backend/db/init.sql)).
- **Docker Compose**: Orchestrates all services ([src/docker-compose.yml](src/docker-compose.yml)).
- **Connection Limiter**: Prevents overload by controlling the number of simultaneous connections to the database. ([`src/backend/connection_limiter/`](src/backend/db/connection_limiter.py)).
- **Health Checks & Statistics**: Endpoints for health checks and cache/load balancer statistics.
- **Rate Limiting**: Load balancer supports rate limiting and strategy switching via API.

## Tasks

The system can support any computational task that will be added to the `/task/` directory and will be mapped in the run_worker.py file.

Currently the system supports three types of hashing tasks: **MD5**, **SHA256**, and **Argon2**. These tasks allow users to submit data (typically strings or passwords) to be securely hashed by the backend workers.

- **MD5**: A fast, legacy hash function. Suitable for checksums but not recommended for password storage due to vulnerabilities.
- **SHA256**: A secure cryptographic hash function from the SHA-2 family. Commonly used for data integrity and digital signatures.
- **Argon2**: A modern, memory-hard password hashing algorithm designed to resist GPU cracking attacks. Recommended for password storage.

### How Tasks Work

1. **Submit a Task**:
   Send a POST request to `/hash/md5`, `/hash/sha256`, or `/hash/argon2` with the data to be hashed.
2. **Queueing**:
   The request is added to the database-backed task queue.
3. **Processing**:
   Worker processes poll the queue, perform the requested hash computation, and store the result in the shared cache.
4. **Retrieval**:
   You can check the status and result of your task via `/task/{task_id}`. Cached results are returned instantly if available.

This architecture allows for scalable, asynchronous processing of computationally intensive hashing operations, making it suitable for high-load scenarios and secure

## Getting Started

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- PostgreSQL

### Setup

1. **Clone the repository**
   ```sh
   git clone https://github.com/zachathanasiadis/scalability-engineering-project.git
   cd scalability-engineering-project/src/

   # Create a new virtual environment
   python -m venv venv

   # Activate it
   source venv/bin/activate

   # Install the requirements
   pip install -r requirements.txt
   ```

2. **Configure environment variables**
   Create a `.env` file in the project root with the following values (edit as needed for your setup):

    ```
   # PostgreSQL Superuser (for initial setup)
   POSTGRES_DB=postgres
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres123

   # Database Configuration
   DB_NAME=your_db
   DB_USER=your_db_user
   DB_PASSWORD=your_password
   DB_HOST=your_db_host
   DB_PORT=5432

   # Connection limitter Configuration:
   DB_CONNECTION_RETRIES=5
   DB_BASE_BACKOFF=0.5
   DB_USER_CONNECTION_LIMIT=4

   # Application Configuration
   APP_NAME=hash-api
   WORKER_NAME=worker

   # Load Balancer Configuration
   LB_STRATEGY=round_robin
   RATE_LIMIT_REQUESTS=100
   RATE_LIMIT_WINDOW=60
   ```

   *Replace all placeholder values above with your own credentials and settings. Suggested values are provided for DB connection limits and load balancer configuration.*

3. **Build and start services**
   ```sh
   docker compose up --build
   ```

   This will start:
   - PostgreSQL database
   - Load balancer (FastAPI)
   - 3 backend API instances
   - 3 worker processes (1 worker per 1 instance)

   To increase the backend API instances, add app entries in the docker-compose.yml and update backends = [], in the load balancer accordingly.

4. **Access the API**
   - Load balancer: [http://localhost:8000](http://localhost:8000)
   - Backend health: `/health`
   - Hash endpoints: `/hash/md5`, `/hash/sha256`, `/hash/argon2`
   - Task status: `/task/{task_id}`

## API Documentation

### Hashing Endpoints

- `POST /hash/md5`
  - **Description:** Queue a task to compute the MD5 hash of the provided data.
  - **Request Body Example:**
    ```json
    { "string": "<your string to hash>" }
    ```
    Replace `<your string to hash>` with the actual value you want to hash.

- `POST /hash/sha256`
  - **Description:** Queue a task to compute the SHA256 hash of the provided data.
  - **Request Body Example:**
    ```json
    { "string": "<your string to hash>" }
    ```
    Replace `<your string to hash>` with the actual value you want to hash.

- `POST /hash/argon2`
  - **Description:** Queue a task to compute the Argon2 hash of the provided data.
  - **Request Body Example:**
    ```json
    { "string": "<your string to hash>" }
    ```
    Replace `<your string to hash>` with the actual value you want to hash.

- `GET /hashes`
  - **Description:** Retrieve all computed hashes.

- `GET /task/{task_id}`
  - **Description:** Get the status and result of a specific hashing task.
  - Replace `{task_id}` with the actual task ID you received when submitting your hash request.

### Health & Cache Endpoints

- `GET /health`
  - **Description:** Check if the backend API is running.

- `GET /cache/stats`
  - **Description:** Get statistics about the shared cache (e.g., hit/miss rates).

- `POST /cache/clear`
  - **Description:** Clear all cached hash results.

### Load Balancer Endpoints

- `GET /lb/health`
  - **Description:** Check if the load balancer is running.

- `GET /lb/stats`
  - **Description:** Get statistics about request distribution and backend health.

- `GET /lb/rate-limits`
  - **Description:** Get current rate limit information.

- `POST /lb/strategy`
  - **Description:** Change the load balancing strategy.
  - **Request Body Example:**
    ```json
    { "strategy": "<round-robin|least-connections>" }
    ```
    Replace `<round-robin|least-connections>` with your desired strategy (either `round-robin` or `least-connections`).

## Development

- Python dependencies are listed in [src/requirements.txt](src/requirements.txt).
- Backend code is in [src/backend/](src/backend/).
- Load balancer code is in [src/loadbalancer/](src/loadbalancer/).

## License

MIT License

## Authors

Szymon Szendzielorz, Zacharias Athanasiadis