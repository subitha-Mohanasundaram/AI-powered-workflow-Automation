import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from .config import settings


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app):
        super().__init__(app)
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        if not request.url.path.startswith("/api"):
            return await call_next(request)

        if settings.rate_limit_requests <= 0:
            return await call_next(request)

        now = time.time()
        window = settings.rate_limit_window_seconds
        limit = settings.rate_limit_requests
        client = request.client.host if request.client else "unknown"
        key = f"{client}:{request.url.path}"
        bucket = self.hits[key]

        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded",
                    "limit": limit,
                    "window_seconds": window,
                },
            )

        bucket.append(now)
        return await call_next(request)

