"""Request logging middleware."""

import time

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


class RequestLoggerMiddleware(BaseHTTPMiddleware):
    """HTTP request/response logging."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        """Process request and log."""
        start_time = time.perf_counter()

        response = await call_next(request)

        elapsed_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            f"{request.method} {request.url.path} → {response.status_code} ({elapsed_ms:.1f}ms)"
        )

        return response
