from fastapi import FastAPI, Request, Response, HTTPException
import httpx
import itertools
import asyncio
import logging
import time
import os
from collections import defaultdict, deque
from typing import Dict, Deque

app = FastAPI()

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s"
)
logger = logging.getLogger("loadbalancer")

# Fixed backend service names (container names or hostnames)
backends = [
    "http://app1:8000",
    "http://app2:8000",
    "http://app3:8000",
]

# Load balancing strategy configuration
STRATEGY = os.getenv("LB_STRATEGY", "round_robin")  # Options: "round_robin", "least_connections"
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "30")) # requests per window
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60")) # window size in seconds
RATE_LIMIT_CLEANUP_INTERVAL = 120  # cleanup old entries every 2 minutes

# Round-robin iterator
backend_iter = itertools.cycle(backends)

# Least connections tracking
backend_connections = {backend: 0 for backend in backends}

# Create asyncio lock for concurrency-safe access
lock = asyncio.Lock()

# Rate limiting storage: IP -> deque of request timestamps
rate_limit_storage: Dict[str, Deque[float]] = defaultdict(deque)
last_cleanup = time.time()

def get_client_ip(request: Request) -> str:
    """Extract client IP from request headers"""
    # Check for forwarded headers first (common in load balancer setups)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()

    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip

    # Fallback to direct client IP
    return request.client.host if request.client else "unknown"

def cleanup_old_entries():
    """Remove old rate limit entries to prevent memory leaks"""
    global last_cleanup
    current_time = time.time()

    if current_time - last_cleanup > RATE_LIMIT_CLEANUP_INTERVAL:
        cutoff_time = current_time - RATE_LIMIT_WINDOW

        # Clean up old entries
        for ip, timestamps in list(rate_limit_storage.items()):
            while timestamps and timestamps[0] < cutoff_time:
                timestamps.popleft()

            # Remove empty entries
            if not timestamps:
                del rate_limit_storage[ip]

        last_cleanup = current_time

async def check_rate_limit(client_ip: str) -> bool:
    """Check if client IP has exceeded rate limit"""
    current_time = time.time()
    cutoff_time = current_time - RATE_LIMIT_WINDOW

    # Get or create timestamp deque for this IP
    timestamps = rate_limit_storage[client_ip]

    # Remove old timestamps outside the window
    while timestamps and timestamps[0] < cutoff_time:
        timestamps.popleft()

    # Check if limit exceeded
    if len(timestamps) >= RATE_LIMIT_REQUESTS:
        return False

    # Add current timestamp
    timestamps.append(current_time)

    # Periodic cleanup
    cleanup_old_entries()

    return True

async def select_backend() -> str:
    """Select backend based on configured strategy"""
    async with lock:
        if STRATEGY == "least_connections":
            # Find backend with minimum connections
            backend = min(backend_connections.keys(), key=lambda b: backend_connections[b])
            backend_connections[backend] += 1
            logger.debug(f"Selected backend {backend} (connections: {backend_connections[backend]})")
            return backend
        else:
            # Default to round-robin
            backend = next(backend_iter)
            logger.debug(f"Selected backend {backend} (round-robin)")
            return backend

async def release_backend(backend: str):
    """Release backend connection (for least connections strategy)"""
    if STRATEGY == "least_connections":
        async with lock:
            backend_connections[backend] = max(0, backend_connections[backend] - 1)
            logger.debug(f"Released backend {backend} (connections: {backend_connections[backend]})")

@app.middleware("http")
async def rate_limited_load_balanced_proxy(request: Request, call_next):
    # Get client IP
    client_ip = get_client_ip(request)

    # Check rate limit
    if not await check_rate_limit(client_ip):
        logger.warning(f"Rate limit exceeded for IP {client_ip}")
        return Response(
            content=f"Rate limit exceeded. Maximum {RATE_LIMIT_REQUESTS} requests per {RATE_LIMIT_WINDOW} seconds.",
            status_code=429,
        )

    # Special handling for internal endpoints
    path = request.url.path
    if path.startswith("/lb/"):
        # For internal loadbalancer endpoints, bypass proxy and call the next middleware
        return await call_next(request)

    # Select backend based on strategy
    backend = await select_backend()

    query = request.url.query
    method = request.method
    headers = dict(request.headers)
    body = await request.body()

    url = f"{backend}{path}"
    logger.info(f"Incoming {method} request from {client_ip} for {path} routed to {backend} (strategy: {STRATEGY})")

    if query:
        url += f"?{query}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
                timeout=None
            )

        # Create a response with the same status code and headers
        request_response = Response(
            content=response.content,
            status_code=response.status_code,
            headers=dict(response.headers)
        )

        logger.info(f"Response {response.status_code} from {backend} for {method} {path}")
        return request_response

    except Exception as e:
        logger.error(f"Error contacting backend retry{backend}: {e}")
        return Response(content=f"Backend Error: {e}", status_code=502)

    finally:
        # Release backend connection for least connections strategy
        await release_backend(backend)

@app.get("/lb/health")
def health_check():
    """Health check endpoint for the load balancer"""
    return {"status": "healthy", "service": "loadbalancer"}

@app.get("/lb/stats")
def get_stats():
    """Get load balancer statistics"""
    return {
        "active_ips": len(rate_limit_storage),
        "strategy": STRATEGY,
        "backend_connections": backend_connections if STRATEGY == "least_connections" else None,
        "rate_limit_config": {
            "requests_per_window": RATE_LIMIT_REQUESTS,
            "window_seconds": RATE_LIMIT_WINDOW
        },
        "backends": backends
    }

@app.get("/lb/rate-limits")
def get_rate_limits():
    """Get current rate limit status for all IPs"""
    current_time = time.time()
    result = {}

    for ip, timestamps in rate_limit_storage.items():
        # Count requests in current window
        cutoff_time = current_time - RATE_LIMIT_WINDOW
        active_requests = sum(1 for ts in timestamps if ts > cutoff_time)

        result[ip] = {
            "requests_in_window": active_requests,
            "requests_remaining": max(0, RATE_LIMIT_REQUESTS - active_requests),
            "window_reset_in": RATE_LIMIT_WINDOW - (current_time - timestamps[0]) if timestamps else 0
        }

    return result

@app.post("/lb/strategy")
async def change_strategy(new_strategy: str):
    """Change load balancing strategy"""
    global STRATEGY

    if new_strategy not in ["round_robin", "least_connections"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid strategy. Must be 'round_robin' or 'least_connections'"
        )

    old_strategy = STRATEGY
    STRATEGY = new_strategy

    # Reset connection counts when switching strategies
    if new_strategy == "least_connections":
        for backend in backends:
            backend_connections[backend] = 0

    logger.info(f"Load balancing strategy changed from {old_strategy} to {new_strategy}")
    return {
        "message": f"Strategy changed from {old_strategy} to {new_strategy}",
        "old_strategy": old_strategy,
        "new_strategy": new_strategy
    }
