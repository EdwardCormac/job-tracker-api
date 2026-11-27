from prometheus_client import Counter, Histogram

REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests handled by the API.",
    ["method", "route", "status_code"],
)

REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "Time spent handling HTTP requests.",
    ["method", "route"],
    buckets=(0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5),
)
