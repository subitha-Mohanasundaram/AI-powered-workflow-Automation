import os
import random
import time
from datetime import datetime

from prometheus_client import Counter, Gauge, Histogram, start_http_server

SERVICE_NAME = os.environ.get("SERVICE_NAME", "payment-service")

BASE_ERROR_RATE = float(os.environ.get("BASE_ERROR_RATE", "0.02"))
SPIKE_ERROR_RATE = float(os.environ.get("SPIKE_ERROR_RATE", "0.35"))

BASE_LATENCY_MS = float(os.environ.get("BASE_LATENCY_MS", "180"))
SPIKE_LATENCY_MS = float(os.environ.get("SPIKE_LATENCY_MS", "1400"))

BASE_DB_POOL_UTIL = float(os.environ.get("BASE_DB_POOL_UTIL", "40"))
SPIKE_DB_POOL_UTIL = float(os.environ.get("SPIKE_DB_POOL_UTIL", "95"))

SPIKE_EVERY_SECONDS = int(os.environ.get("SPIKE_EVERY_SECONDS", "120"))
SPIKE_DURATION_SECONDS = int(os.environ.get("SPIKE_DURATION_SECONDS", "30"))

LOG_FILE = os.environ.get("LOG_FILE", "/var/log/sim/app.log")

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "status"],
)

HTTP_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency",
    ["service"],
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0, 3.0),
)

DB_CONN_ACTIVE = Gauge(
    "db_connections_active",
    "Active DB connections",
    ["service"],
)

DB_POOL_UTIL = Gauge(
    "db_pool_utilization",
    "DB connection pool utilization percent",
    ["service"],
)


def in_spike_window(now: float) -> bool:
    if SPIKE_EVERY_SECONDS <= 0:
        return False
    t = int(now) % SPIKE_EVERY_SECONDS
    return t < SPIKE_DURATION_SECONDS


def log_line(message: str) -> None:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def main() -> None:
    start_http_server(9000)
    log_line(f"{datetime.utcnow().isoformat()}Z INFO simulator started service={SERVICE_NAME}")

    while True:
        now = time.time()
        spiking = in_spike_window(now)

        error_rate = SPIKE_ERROR_RATE if spiking else BASE_ERROR_RATE
        latency_ms = SPIKE_LATENCY_MS if spiking else BASE_LATENCY_MS
        db_util = SPIKE_DB_POOL_UTIL if spiking else BASE_DB_POOL_UTIL

        # Simulate 50 requests per second.
        requests_per_tick = 50
        errors = 0
        for _ in range(requests_per_tick):
            is_error = random.random() < error_rate
            status = "500" if is_error else "200"
            HTTP_REQUESTS_TOTAL.labels(service=SERVICE_NAME, status=status).inc()

            # latency distribution
            sample_ms = max(10.0, random.gauss(latency_ms, latency_ms * 0.15))
            HTTP_LATENCY.labels(service=SERVICE_NAME).observe(sample_ms / 1000.0)

            if is_error:
                errors += 1

        # DB gauges
        DB_POOL_UTIL.labels(service=SERVICE_NAME).set(db_util)
        DB_CONN_ACTIVE.labels(service=SERVICE_NAME).set(int(5 + (db_util / 100.0) * 45))

        if spiking:
            log_line(
                f"{datetime.utcnow().isoformat()}Z ERROR payment failed service={SERVICE_NAME} "
                f"error_rate={error_rate:.2f} latency_ms={latency_ms:.0f} db_util={db_util:.0f}"
            )
        else:
            if errors > 0:
                log_line(f"{datetime.utcnow().isoformat()}Z WARN transient errors={errors} service={SERVICE_NAME}")

        time.sleep(1)


if __name__ == "__main__":
    main()
