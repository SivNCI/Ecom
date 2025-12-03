# app/limiter.py
from fastapi.responses import PlainTextResponse
from redis.asyncio import Redis
from app.metrics import REQUEST_STATUS

# Redis client (shared)
redis_client: Redis = None
adaptive_sha = None

# Adaptive parameters
BASE_LIMIT = 15      # default allowed requests per WINDOW
MIN_LIMIT = 3
WINDOW = 60          # seconds

RISK_KEY_PREFIX = "risk:"   # per-ip risk (incremented when blocked)


async def init_redis_lua():
    """
    Initialize redis client and load the Lua script into Redis.
    This script increments the per-IP key and returns remaining tokens or -1.
    """
    global redis_client, adaptive_sha
    redis_client = Redis(host="localhost", port=6379, decode_responses=True)

    lua_script = """
    -- KEYS[1] => count_key
    -- ARGV[1] => limit
    -- ARGV[2] => window
    local key = KEYS[1]
    local limit = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])

    local current = redis.call("INCR", key)
    if current == 1 then
        redis.call("EXPIRE", key, window)
    end

    if current > limit then
        return -1
    else
        return limit - current
    end
    """

    adaptive_sha = await redis_client.script_load(lua_script)
    print("Adaptive Lua script loaded.")


async def adaptive_rate_limit_middleware(request, call_next):
    """
    Adaptive middleware:
    - Reads a per-IP "risk" value from Redis (risk:{ip}). Higher risk => lower limit.
    - Computes effective limit = max(BASE_LIMIT - risk, MIN_LIMIT)
    - Uses Lua in Redis (EVALSHA) to atomically increment and check counts.
    - On block: increments REQUEST_STATUS(status=429) and increments risk key.
    - On allow: lets request pass (metrics middleware will count 200).
    """
    ip = request.client.host
    count_key = f"rate:{ip}"
    risk_key = f"{RISK_KEY_PREFIX}{ip}"

    # Read risk (may be None)
    try:
        risk_raw = await redis_client.get(risk_key)
    except Exception as e:
        # If Redis read fails, be conservative (use base limit)
        print("Redis GET risk error:", e)
        risk_raw = None

    try:
        risk = int(risk_raw) if risk_raw is not None else 0
    except:
        risk = 0

    # Compute adaptive limit
    effective_limit = BASE_LIMIT - risk
    if effective_limit < MIN_LIMIT:
        effective_limit = MIN_LIMIT

    # Use universal execute_command (works across redis-py async versions)
    try:
        remaining = await redis_client.execute_command(
            "EVALSHA",
            adaptive_sha,
            1,                    # number of KEYS
            count_key,            # KEYS[1]
            str(effective_limit), # ARGV[1] (must be string)
            str(WINDOW)           # ARGV[2]
        )
    except Exception as e:
        # Log and return 500 — metrics for 500
        print("Evalsha error:", e)
        try:
            REQUEST_STATUS.labels(status="500", ip=ip).inc()
        except Exception:
            pass
        return PlainTextResponse("Adaptive Rate Error", status_code=500)

    # If blocked
    if int(remaining) == -1:
        # increment risk score (so repeated abusers get tighter limit)
        try:
            await redis_client.incr(risk_key)
            await redis_client.expire(risk_key, 300)  # keep risk for 5 minutes
        except Exception as e:
            print("Failed to increment risk:", e)

        # increment prometheus 429 counter
        try:
            REQUEST_STATUS.labels(status="429", ip=ip).inc()
        except Exception:
            pass

        return PlainTextResponse("Too Many Requests (Adaptive Limit)", status_code=429)

    # Allowed — let the next handler/middleware process the request.
    # Note: metrics middleware (earlier in chain) will record the 200 status for successful responses.
    return await call_next(request)
