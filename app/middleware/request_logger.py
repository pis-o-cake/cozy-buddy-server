"""요청 액세스 로그 미들웨어 (loguru, 영어 하드코딩)."""

import time
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response
from loguru import logger


def register_request_logger(app: FastAPI) -> None:
    @app.middleware("http")
    async def log_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "{} {} -> {} ({:.1f}ms)",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
        return response
