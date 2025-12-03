# app/main.py
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
import time

from app.limiter import adaptive_rate_limit_middleware, init_redis_lua
from app.metrics import REQUEST_COUNT, REQUEST_LATENCY, REQUEST_STATUS

from prometheus_client import generate_latest

app = FastAPI()
templates = Jinja2Templates(directory="app/templates")


# Startup — initialize redis + lua
@app.on_event("startup")
async def startup_event():
    await init_redis_lua()


# Metrics middleware (runs BEFORE rate limiter)
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    ip = request.client.host
    method = request.method
    endpoint = request.url.path

    # increment request count
    try:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, ip=ip).inc()
    except Exception:
        pass

    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start

    # record latency
    try:
        REQUEST_LATENCY.labels(endpoint=endpoint).observe(elapsed)
    except Exception:
        pass

    # record status — this will count 200 for successful flows.
    try:
        REQUEST_STATUS.labels(status=str(response.status_code), ip=ip).inc()
    except Exception:
        pass

    return response


# Rate limiter middleware (runs AFTER metrics middleware)
@app.middleware("http")
async def limiter_middleware(request: Request, call_next):
    return await adaptive_rate_limit_middleware(request, call_next)


# Routes and templates
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("cartpage.html", {"request": request})


@app.post("/add_to_cart")
async def add_to_cart():
    # simulate processing
    return {"message": "Item added to cart"}


# Prometheus endpoint
@app.get("/metrics")
async def metrics():
    return PlainTextResponse(generate_latest(), media_type="text/plain")
