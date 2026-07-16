"""전역 예외 → HTTP 응답 변환.

응답 형식은 WS 오류 메시지(설계서 §5-1)와 동일한 `{code, message}` — 클라이언트가
전송 계층과 무관하게 같은 파서를 쓴다. message는 i18n, 로그는 영어.
"""

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.exceptions import AppError
from app.core.i18n import t


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "request failed: {} {} -> {} ({})", request.method, request.url.path, exc.code, exc
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": t(exc.message_key, **exc.params)},
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error: {} {}", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content={"code": "internal_error", "message": t("errors.internal")},
        )
