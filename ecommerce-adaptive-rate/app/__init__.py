# __init__.py
# This makes 'app' a Python package and helps Uvicorn resolve imports.

from .limiter import adaptive_rate_limit_middleware, init_redis_lua
from .metrics import REQUEST_COUNT, REQUEST_LATENCY, REQUEST_STATUS

