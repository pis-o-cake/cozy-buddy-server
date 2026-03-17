"""Logging configuration module."""

import sys

from loguru import logger

from app.config import settings


def setup_logging() -> None:
    """Initialize loguru logger."""
    logger.remove()

    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            level=settings.log_level,
            format=(
                "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                "<level>{level: <8}</level> | "
                "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
                "<level>{message}</level>"
            ),
        )

    logger.add(
        settings.log_file,
        level=settings.log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip",
        encoding="utf-8",
    )
