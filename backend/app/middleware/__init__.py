import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("sportshub.middleware")


class RequestLoggingAndRateLimitMiddleware(BaseHTTPMiddleware):
    """
    Logs HTTP requests with latency and enforces a generous sliding-window rate limit per IP.
    """

    def __init__(self, app, max_requests_per_minute: int = 300):
        super().__init__(app)
        self.max_requests = max_requests_per_minute
        self.window_seconds = 60.0
        self.hits: Dict[str, Deque[float]] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.monotonic()

        bucket = self.hits[client_ip]
        while bucket and (now - bucket[0]) > self.window_seconds:
            bucket.popleft()

        if len(bucket) >= self.max_requests:
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please try again shortly."},
            )
        bucket.append(now)

        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "%s %s -> %d (%.1f ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

