"""
Per-user/IP sliding-window rate limiter.

Rate limiting is keyed on (user_id_header OR client_ip) so a single
actor cannot exhaust the global request budget.

Note: this in-process implementation resets on restart and is not
shared across multiple workers.  For multi-worker deployments, replace
the deque store with a Redis-backed solution (e.g. slowapi + redis).
"""
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings
from .logging_config import get_logger

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        # {rate_key: deque[float]}  — stores request timestamps
        self.hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        limit = settings.rate_limit_requests
        if limit <= 0:
            return await call_next(request)

        now = time.time()
        window = settings.rate_limit_window_seconds

        # Prefer the user-supplied X-User-ID header; fall back to IP.
        user_id = request.headers.get("X-User-ID", "").strip()
        client_ip = request.client.host if request.client else "unknown"
        rate_key = f"{user_id or client_ip}:{request.url.path}"

        bucket = self.hits[rate_key]

        # Evict timestamps outside the current window.
        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= limit:
            logger.warning(
                "Rate limit exceeded | key=%s | limit=%d | window=%ds",
                rate_key,
                limit,
                window,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": window,
                    "retry_after": int(window - (now - bucket[0])),
                },
                headers={"Retry-After": str(int(window - (now - bucket[0])))},
            )

        bucket.append(now)
        return await call_next(request)
