"""Scenario scheduler."""

from loguru import logger


class ScenarioScheduler:
    """APScheduler-based scenario scheduler."""

    def __init__(self) -> None:
        self._scheduler = None

    async def initialize(self) -> None:
        """Initialize scheduler."""
        # TODO: APScheduler setup
        logger.info("Scenario scheduler initialized")

    async def shutdown(self) -> None:
        """Shutdown scheduler."""
        logger.info("Scenario scheduler shutdown")
