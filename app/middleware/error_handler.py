"""Global error handler middleware."""

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger

from app.core.exceptions import CozyBuddyError
from app.core.i18n import t


async def cozy_buddy_error_handler(
    request: Request, exc: CozyBuddyError
) -> JSONResponse:
    """Handle CozyBuddy custom exceptions."""
    logger.error(f"[{exc.code}] {exc.message} | path={request.url.path}")
    return JSONResponse(
        status_code=400,
        content={"code": exc.code, "message": exc.message},
    )


async def global_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle uncaught exceptions."""
    logger.exception(f"Unhandled exception | path={request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": t("error.internal")},
    )
