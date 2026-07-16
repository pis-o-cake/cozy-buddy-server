"""loguru 기반 로깅 설정.

로그 메시지는 전 구간 영어 하드코딩 — 언어팩 사용 금지 (설계서 §13-3, 로케일 무관 검색성).
"""

import logging
import sys

from loguru import logger

from app.config import get_settings


class _InterceptHandler(logging.Handler):
    """표준 logging → loguru 브리지 (uvicorn·sqlalchemy 로그 통합)."""

    def emit(self, record: logging.LogRecord) -> None:
        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno
        logger.opt(depth=6, exception=record.exc_info).log(level, record.getMessage())


def setup_logging() -> None:
    """loguru 싱크를 구성하고 표준 logging을 가로챈다. 앱 기동 시 1회 호출."""
    settings = get_settings()
    logger.remove()
    logger.add(
        sys.stderr,
        level=settings.log_level.upper(),
        backtrace=settings.debug,
        diagnose=settings.debug,
    )
    logging.basicConfig(handlers=[_InterceptHandler()], level=0, force=True)
