# app/metrics.py
from prometheus_client import Counter, Histogram

# Count requests (method, endpoint, ip)
REQUEST_COUNT = Counter(
    "request_count_total",
    "Total requests",
    ["method", "endpoint", "ip"],
)

# Count responses by status code (status, ip)
REQUEST_STATUS = Counter(
    "request_status_total",
    "HTTP responses by status code",
    ["status", "ip"],
)

# Request latency histogram (endpoint)
REQUEST_LATENCY = Histogram(
    "request_latency_seconds",
    "Request latency",
    ["endpoint"],
)
