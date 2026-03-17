"""Scenario domain service."""

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ScenarioError
from app.domain.scenario import crud
from app.domain.scenario.models import Scenario


class ScenarioService:
    """Scenario management service."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def create_scenario(self, **kwargs: Any) -> Scenario:
        """Create a scenario."""
        return await crud.create_scenario(self._db, **kwargs)

    async def get_all_scenarios(self) -> list[Scenario]:
        """Get all scenarios."""
        return await crud.get_all_scenarios(self._db)

    async def activate_scenario(self, *, name: str) -> dict[str, Any]:
        """Activate a scenario."""
        scenario = await crud.get_scenario_by_name(self._db, name=name)
        if not scenario:
            raise ScenarioError(message=f"Scenario not found: {name}")

        # TODO: Execute actions via DeviceService
        logger.info(f"Scenario executed: {name}, {len(scenario.actions)} actions")
        return {
            "scenario": name,
            "actions_count": len(scenario.actions),
            "status": "executed",
        }
