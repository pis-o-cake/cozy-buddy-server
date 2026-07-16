"""scenario 도메인 DB 접근."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.scenario.models import Scenario, ScenarioAction


async def list_scenarios(session: AsyncSession) -> list[Scenario]:
    return list((await session.scalars(sa.select(Scenario).order_by(Scenario.id))).all())


async def get_scenario(session: AsyncSession, scenario_id: int) -> Scenario | None:
    return await session.get(Scenario, scenario_id)


async def get_by_name(session: AsyncSession, name: str) -> Scenario | None:
    return await session.scalar(sa.select(Scenario).where(Scenario.name == name))


async def get_actions(session: AsyncSession, scenario_id: int) -> list[ScenarioAction]:
    rows = await session.scalars(
        sa.select(ScenarioAction)
        .where(ScenarioAction.scenario_id == scenario_id)
        .order_by(ScenarioAction.order)
    )
    return list(rows.all())


async def create_scenario(
    session: AsyncSession, *, name: str, triggers: list, enabled: bool, actions: list[dict]
) -> Scenario:
    scenario = Scenario(name=name, triggers=triggers, enabled=enabled)
    session.add(scenario)
    await session.flush()
    for action in actions:
        session.add(ScenarioAction(scenario_id=scenario.id, **action))
    await session.commit()
    await session.refresh(scenario)
    return scenario


async def delete_scenario(session: AsyncSession, scenario: Scenario) -> None:
    for action in await get_actions(session, scenario.id):
        await session.delete(action)
    await session.delete(scenario)
    await session.commit()
