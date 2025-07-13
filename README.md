# Scalability Engineering Prototype Assignment

This project is a scalable, containerized task processing system built with FastAPI, PostgreSQL, and Docker. It features a load balancer, multiple backend API instances, worker processes, and a shared cache using the database.

## Features

- **Load Balancer**: Distributes requests to backend API instances using round-robin or least-connections strategies ([src/loadbalancer/loadbalancer.py](src/loadbalancer/loadbalancer.py)).
- **Backend API**: Provides endpoints for hash calculations (MD5, SHA256, Argon2) and Fibonacci computation ([src/backend/main.py](src/backend/main.py)).
- **Task Queue**: Tasks are queued in the database and processed asynchronously by workers ([src/backend/queue_service/queue_manager.py](src/backend/queue_service/queue_manager.py)).
- **Workers**: Poll the queue and process tasks ([src/backend/worker/worker.py](src/backend/worker/worker.py), [src/run_worker.py](src/run_worker.py)).
- **Shared Cache**: Results are cached in the database for fast retrieval ([src/backend/db/shared_cache.py](src/backend/db/shared_cache.py)).
- **PostgreSQL Database**: Stores tasks, workers, and cache entries ([src/backend/db/db_manager.py](src/backend/db/db_manager.py), [src/backend/db/init.sql](src/backend/db/init.sql)).
- **Docker Compose**: Orchestrates all services ([src/docker-compose.yml](src/docker-compose.yml)).

## Hashing Tasks

The system supports three types of hashing tasks: **MD5**, **SHA256**, and **Argon2**. These tasks allow users to submit data (typically strings or passwords) to be securely hashed by the backend workers.

- **MD5**: A fast, legacy hash function. Suitable for checksums but not recommended for password storage due to vulnerabilities.
- **SHA256**: A secure cryptographic hash function from the SHA-2 family. Commonly used for data integrity and digital signatures.
- **Argon2**: A modern, memory-hard password hashing algorithm designed to resist GPU cracking attacks. Recommended for password storage.

### How Hashing Tasks Work

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
   git clone <your-repo-url>
   cd ScalabilityEngineeringProject/src
   ```

2. **Configure environment variables**
   Edit [.env](.env) for database and worker settings.

3. **Build and start services**
   ```sh
   docker compose up --build
   ```

   This will start:
   - PostgreSQL database
   - Load balancer (FastAPI)
   - 3 backend API instances
   - 3 worker processes

4. **Access the API**
   - Load balancer: [http://localhost:8000](http://localhost:8000)
   - Backend health: `/health`
   - Hash endpoints: `/hash/md5`, `/hash/sha256`, `/hash/argon2`
   - Task status: `/task/{task_id}`

## API Endpoints

- `POST /hash/md5` — Queue MD5 hash calculation
- `POST /hash/sha256` — Queue SHA256 hash calculation
- `POST /hash/argon2` — Queue Argon2 hash calculation
- `GET /hashes` — Get all computed hashes
- `GET /task/{task_id}` — Get status/result of a task
- `GET /health` — Health check
- `GET /cache/stats` — Cache statistics
- `POST /cache/clear` — Clear cache

## Load Balancer Endpoints

- `GET /lb/health` — Health check
- `GET /lb/stats` — Load balancer stats
- `GET /lb/rate-limits` — Rate limit info
- `POST /lb/strategy` — Change load balancing strategy

## Development

- Python dependencies are listed in [src/requirements.txt](src/requirements.txt).
- Backend code is in [src/backend/](src/backend/).
- Load balancer code is in [src/loadbalancer/](src/loadbalancer/).

## License

MIT License

## Authors

Szymon Szendzielorz, Zacharias Athanasiadis