import time
import aioredis
from fastapi import Request, status
from fastapi.responses import JSONResponse

# Redis configuration
redis_client = None
RATE_LIMIT = 15  # requests
TIME_WINDOW = 60  # seconds


async def init_redis_client():
    global redis_client
    redis_client = await aioredis.from_url("redis://localhost", decode_responses=True)


async def rate_limit_middleware(request: Request, call_next):
    global redis_client
    if not redis_client:
        redis_client = await aioredis.from_url("redis://localhost", decode_responses=True)

    ip = request.client.host
    endpoint = request.url.path
    key = f"rate:{ip}:{endpoint}"

    current_time = int(time.time())
    window_start = current_time - TIME_WINDOW

    # Remove outdated timestamps
    await redis_client.zremrangebyscore(key, 0, window_start)

    # Count remaining requests
    count = await redis_client.zcard(key)

    if count >= RATE_LIMIT:
        return JSONResponse(
            content={
                "error": "🚫 Throttled: rate_limit_exceeded",
                "detail": f"Limit of {RATE_LIMIT} per {TIME_WINDOW}s exceeded",
            },
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    # Add current request timestamp
    await redis_client.zadd(key, {str(current_time): current_time})
    await redis_client.expire(key, TIME_WINDOW)

    # Continue request
    response = await call_next(request)
    return response
