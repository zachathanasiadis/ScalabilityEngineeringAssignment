# Scalable Hash API System

A highly scalable hash computation API system demonstrating load balancing, rate limiting, caching, and distributed task processing.

## 🏗️ Architecture Overview

The system consists of several components working together:

### 1. **Load Balancer** (`loadbalancer/`)
- **Rate Limiting**: 100 requests per minute per IP
- **Two Load Balancing Strategies**:
  - **Round Robin**: Distributes requests evenly across backends
  - **Least Connections**: Routes to backend with fewest active connections
- **Health Checks**: Monitors backend health
- **Runtime Strategy Switching**: Change strategies without restart

### 2. **API Instances** (`main.py`)
- **Stateless**: No in-memory state, all data persists in database/cache
- **Horizontally Scalable**: Can run multiple instances
- **Caching Integrated**: Checks cache before queuing tasks
- **Database Integration**: All instances share the same database

### 3. **Workers** (`worker/`)
- **Distributed Task Processing**: Multiple workers process tasks concurrently
- **Task Queue**: Database-backed queue system
- **Pluggable Handlers**: Easy to add new task types
- **Auto-Caching**: Results are cached automatically

### 4. **Custom Caching** (`cache/`)
- **Thread-Safe**: Built for concurrent access
- **TTL Support**: Automatic expiration
- **LRU Eviction**: Memory-efficient
- **No External Dependencies**: Pure Python implementation

### 5. **Database** (`db/`)
- **PostgreSQL**: Reliable task queue and result storage
- **ACID Compliance**: Ensures data consistency
- **Connection Pooling**: Efficient resource usage

## 🚀 Quick Start

### Using Docker Compose (Recommended)

```bash
# Start the entire system
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f

# Scale workers
docker-compose up -d --scale worker1=2 --scale worker2=3

# Stop system
docker-compose down
```

### Manual Setup

1. **Start PostgreSQL Database**:
   ```bash
   # Using Docker
   docker run -d --name hashdb \
     -e POSTGRES_DB=hashdb \
     -e POSTGRES_USER=hashuser \
     -e POSTGRES_PASSWORD=hashpass \
     -p 5432:5432 postgres:15
   ```

2. **Set Environment Variables**:
   ```bash
   export DB_NAME=hashdb
   export DB_USER=hashuser
   export DB_PASSWORD=hashpass
   export DB_HOST=localhost
   export DB_PORT=5432
   ```

3. **Start Workers**:
   ```bash
   python run_worker.py &
   python run_worker.py &
   python run_worker.py &
   ```

4. **Start API Instances**:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8001 &
   uvicorn main:app --host 0.0.0.0 --port 8002 &
   uvicorn main:app --host 0.0.0.0 --port 8003 &
   ```

5. **Start Load Balancer**:
   ```bash
   cd loadbalancer
   uvicorn loadbalancer:app --host 0.0.0.0 --port 8000
   ```

## 📡 API Endpoints

### Hash Operations
- `POST /hash/md5` - Queue MD5 hash calculation
- `POST /hash/sha256` - Queue SHA256 hash calculation
- `GET /task/{task_id}` - Get task status and result
- `GET /hashes` - Get all computed hashes

### System Management
- `GET /health` - Health check
- `GET /cache/stats` - Cache statistics
- `POST /cache/clear` - Clear cache

### Load Balancer Management
- `GET /lb/health` - Load balancer health
- `GET /lb/stats` - Load balancer statistics
- `GET /lb/rate-limits` - Rate limit status
- `POST /lb/strategy` - Change load balancing strategy

## 📊 Usage Examples

### Basic Hash Calculation
```bash
# Queue MD5 calculation
curl -X POST "http://localhost:8000/hash/md5" \
  -H "Content-Type: application/json" \
  -d '{"string": "hello world"}'

# Response
{
  "task_id": 123,
  "status": "queued",
  "message": "MD5 hash calculation queued"
}

# Check task status
curl "http://localhost:8000/task/123"

# Response
{
  "id": 123,
  "type": "md5",
  "status": "completed",
  "result": {
    "original_string": "hello world",
    "md5_hash": "5d41402abc4b2a76b9719d911017c592",
    "execution_time_seconds": 0.001
  }
}
```

### Cached Response
```bash
# Second request for same string returns cached result
curl -X POST "http://localhost:8000/hash/md5" \
  -H "Content-Type: application/json" \
  -d '{"string": "hello world"}'

# Response (immediate)
{
  "result": {
    "original_string": "hello world",
    "md5_hash": "5d41402abc4b2a76b9719d911017c592",
    "execution_time_seconds": 0.001
  },
  "source": "cache"
}
```

### Load Balancer Management
```bash
# Check current strategy
curl "http://localhost:8000/lb/stats"

# Change to least connections
curl -X POST "http://localhost:8000/lb/strategy?new_strategy=least_connections"

# Check rate limits
curl "http://localhost:8000/lb/rate-limits"
```

## 🔧 Configuration

### Load Balancer Settings
```python
# In loadbalancer/loadbalancer.py
RATE_LIMIT_REQUESTS = 100      # requests per window
RATE_LIMIT_WINDOW = 60         # window size in seconds
LB_STRATEGY = "round_robin"    # or "least_connections"
```

### Cache Settings
```python
# In cache/cache_manager.py
default_ttl = 300              # 5 minutes
max_size = 1000               # 1000 items max
```

### Backend Configuration
```python
# In loadbalancer/loadbalancer.py
backends = [
    "http://app1:8000",
    "http://app2:8000",
    "http://app3:8000"
]
```

## 📈 Scalability Features

### 1. **Horizontal Scaling**
- Add more API instances: `docker-compose up -d --scale app1=5`
- Add more workers: `docker-compose up -d --scale worker1=10`

### 2. **Load Balancing Strategies**
- **Round Robin**: Even distribution
- **Least Connections**: Optimal for varying request processing times

### 3. **Rate Limiting**
- Per-IP rate limiting prevents abuse
- Configurable limits and windows
- Returns proper HTTP 429 responses

### 4. **Caching**
- Reduces database load
- Improves response times
- Automatic cache warming from workers

### 5. **Database-Backed Queue**
- Persistent task queue
- ACID compliance
- Survives system restarts

## 🏃‍♂️ Performance Testing

### Load Testing
```bash
# Install Apache Bench
sudo apt-get install apache2-utils

# Test with 1000 requests, 10 concurrent
ab -n 1000 -c 10 -p data.json -T application/json http://localhost:8000/hash/md5

# Test rate limiting
ab -n 200 -c 20 http://localhost:8000/lb/health
```

### Monitoring
```bash
# Watch cache stats
watch -n 1 'curl -s http://localhost:8000/cache/stats | jq'

# Watch load balancer stats
watch -n 1 'curl -s http://localhost:8000/lb/stats | jq'

# Watch database activity
docker-compose exec db psql -U hashuser -d hashdb -c "SELECT status, COUNT(*) FROM tasks GROUP BY status;"
```

## 🔍 Troubleshooting

### Common Issues

1. **Database Connection Failed**
   ```bash
   # Check database is running
   docker-compose ps db

   # Check logs
   docker-compose logs db
   ```

2. **Workers Not Processing Tasks**
   ```bash
   # Check worker logs
   docker-compose logs worker1

   # Check task queue
   curl http://localhost:8000/task/1
   ```

3. **Rate Limiting Too Aggressive**
   ```bash
   # Check current limits
   curl http://localhost:8000/lb/rate-limits

   # Adjust in loadbalancer.py
   RATE_LIMIT_REQUESTS = 1000
   ```

### Health Checks
```bash
# System health
curl http://localhost:8000/health
curl http://localhost:8000/lb/health

# Database health
docker-compose exec db pg_isready -U hashuser -d hashdb
```

## 🛠️ Development

### Running Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio

# Run tests
pytest tests/
```

### Code Structure
```
├── main.py                 # Main FastAPI application
├── loadbalancer/          # Load balancer with rate limiting
├── worker/               # Distributed task processing
├── cache/                # Custom caching implementation
├── db/                   # Database management
├── queue_service/        # Task queue system
├── tasks/                # Task handlers (MD5, SHA256)
├── docker-compose.yml    # Complete system setup
└── README.md            # This file
```

## 📋 Assignment Compliance

✅ **Load Balancer**: Implemented with rate limiting
✅ **Two Strategies**: Round-robin and least connections
✅ **Multiple Instances**: Horizontally scalable API instances
✅ **Workers**: Distributed task processing
✅ **Shared Database**: All instances use same PostgreSQL
✅ **Custom Caching**: Thread-safe, TTL-based cache
✅ **Stateless**: No in-memory state in endpoints
✅ **Consistent Results**: All instances return same data

## 🎯 Key Improvements Made

1. **Removed In-Memory State**: Eliminated `str_to_hash256_mappings` and `str_to_md5_mappings`
2. **Integrated Caching**: Cache checks before queuing, results cached after completion
3. **Added Rate Limiting**: 100 requests per minute per IP with proper HTTP responses
4. **Dual Load Balancing**: Round-robin and least connections strategies
5. **Health Checks**: Comprehensive monitoring endpoints
6. **Docker Compose**: Complete system orchestration
7. **Proper Error Handling**: Graceful failure handling throughout

The system now fully complies with scalability engineering principles and assignment requirements!