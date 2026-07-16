"""scenario API (설계서 §5-2 — /api/scenarios)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.scenario import crud, service
from app.domain.scenario.schemas import ActionOut, RunResult, ScenarioCreate, ScenarioOut

PREFIX = "/api/scenarios"
router = APIRouter(tags=["scenario"])


@router.get("", response_model=list[ScenarioOut])
async def list_scenarios(session: AsyncSession = Depends(get_session)) -> list[ScenarioOut]:
    return [ScenarioOut.model_validate(s) for s in await crud.list_scenarios(session)]


@router.post("", response_model=ScenarioOut)
async def create_scenario(
    body: ScenarioCreate, session: AsyncSession = Depends(get_session)
) -> ScenarioOut:
    if await crud.get_by_name(session, body.name) is not None:
        raise ConflictError(f"scenario '{body.name}' already exists")
    scenario = await crud.create_scenario(
        session,
        name=body.name,
        triggers=body.triggers,
        enabled=body.enabled,
        actions=[a.model_dump() for a in body.actions],
    )
    service.sync_schedule(scenario)  # schedule 트리거 즉시 반영 (§9-1)
    return ScenarioOut.model_validate(scenario)


@router.get("/{scenario_id}", response_model=ScenarioOut)
async def get_scenario(
    scenario_id: int, session: AsyncSession = Depends(get_session)
) -> ScenarioOut:
    scenario = await crud.get_scenario(session, scenario_id)
    if scenario is None:
        raise NotFoundError(f"scenario {scenario_id} not found")
    return ScenarioOut.model_validate(scenario)


@router.get("/{scenario_id}/actions", response_model=list[ActionOut])
async def get_actions(
    scenario_id: int, session: AsyncSession = Depends(get_session)
) -> list[ActionOut]:
    return [ActionOut.model_validate(a) for a in await crud.get_actions(session, scenario_id)]


@router.delete("/{scenario_id}", status_code=204)
async def delete_scenario(scenario_id: int, session: AsyncSession = Depends(get_session)) -> None:
    scenario = await crud.get_scenario(session, scenario_id)
    if scenario is None:
        raise NotFoundError(f"scenario {scenario_id} not found")
    scenario.enabled = False
    service.sync_schedule(scenario)  # 잡 제거
    await crud.delete_scenario(session, scenario)


@router.post("/{scenario_id}/run", response_model=RunResult)
async def run_scenario(
    scenario_id: int, session: AsyncSession = Depends(get_session)
) -> RunResult:
    scenario = await crud.get_scenario(session, scenario_id)
    if scenario is None:
        raise NotFoundError(f"scenario {scenario_id} not found")
    return await service.execute_scenario(session, scenario)
