# __init__.py
# This makes 'app' a Python package and helps Uvicorn resolve imports.

from .limiter import rate_limit_middleware, init_redis_client
