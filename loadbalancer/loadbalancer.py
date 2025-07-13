from fastapi import FastAPI, Request, Response
import httpx
import itertools
import asyncio
import logging

app = FastAPI()

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("loadbalancer")

# Fixed backend service names (container names or hostnames)
backends = [
    "http://app1:8000",
    "http://app2:8000",
    "http://app3:8000",
    "http://app4:8000",
    "http://app5:8000"
]

# Round-robin iterator
backend_iter = itertools.cycle(backends)

# Create asyncio lock for concurrency-safe access
lock = asyncio.Lock()

@app.middleware("http")
async def round_robin_proxy(request: Request):
    async with lock:
        backend = next(backend_iter) # safely pick next backend
    path = request.url.path
    query = request.url.query
    method = request.method
    headers = dict(request.headers)
    body = await request.body()

    url = f"{backend}{path}"
    logger.info(f"Incoming {method} request for {path} routed to {backend}")

    if query:
        url += f"?{query}"
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
                timeout=10.0
            )
        logger.info(f"Response {response.status_code} from {backend} for {method} {path}")
        return response
    except httpx.RequestError as e:
        logger.error(f"Error contacting backend {backend}: {e}")
        return Response(content=f"Backend unreachable: {e}", status_code=502)
