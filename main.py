import asyncio
from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from app.limiter import rate_limit_middleware, init_redis_client

app = FastAPI(title="Adaptive Rate Limiter - Add to Cart Demo")

templates = Jinja2Templates(directory="app/templates")

# ---------------------------
# Prometheus metrics
# ---------------------------
REQUEST_COUNT = Counter("request_count", "Total requests", ["endpoint"])
REQUEST_LATENCY = Histogram("request_latency_seconds", "Request latency", ["endpoint"])


@app.on_event("startup")
async def startup_event():
    # Initialize Redis connection
    await init_redis_client()
    print("✅ Connected to Redis successfully.")


@app.middleware("http")
async def add_metrics_and_rate_limit(request: Request, call_next):
    endpoint = request.url.path
    REQUEST_COUNT.labels(endpoint=endpoint).inc()

    with REQUEST_LATENCY.labels(endpoint=endpoint).time():
        response = await rate_limit_middleware(request, call_next)
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("cartpage.html", {"request": request})


@app.post("/add_to_cart", response_class=JSONResponse)
async def add_to_cart(request: Request):
    # Simulated add-to-cart logic
    await asyncio.sleep(0.1)
    return JSONResponse(
        content={"message": "✅ Item added successfully!"},
        status_code=status.HTTP_200_OK,
    )


@app.get("/metrics")
async def metrics():
    return HTMLResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)
