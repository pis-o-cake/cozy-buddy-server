"""Scenario domain CRUD."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scenario.models import Scenario


async def create_scenario(
    db: AsyncSession,
    *,
    name: str,
    actions: list[dict[str, Any]],
    trigger: str = "manual",
) -> Scenario:
    """Create a scenario."""
    scenario = Scenario(name=name, actions=actions, trigger=trigger)
    db.add(scenario)
    await db.flush()
    return scenario


async def get_scenario_by_name(db: AsyncSession, *, name: str) -> Scenario | None:
    """Get scenario by name."""
    stmt = select(Scenario).where(Scenario.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_scenarios(db: AsyncSession) -> list[Scenario]:
    """Get all scenarios."""
    stmt = select(Scenario)
    result = await db.execute(stmt)
    return list(result.scalars().all())
