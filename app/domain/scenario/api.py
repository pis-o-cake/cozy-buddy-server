"""Scenario domain API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domain.scenario.schemas import ScenarioCreate, ScenarioResponse
from app.domain.scenario.service import ScenarioService

router = APIRouter()


@router.post("", response_model=ScenarioResponse)
async def create_scenario(
    request: ScenarioCreate,
    db: AsyncSession = Depends(get_db),
) -> ScenarioResponse:
    """Create a scenario."""
    service = ScenarioService(db)
    scenario = await service.create_scenario(
        name=request.name,
        actions=[a.model_dump() for a in request.actions],
        trigger=request.trigger,
    )
    return ScenarioResponse.model_validate(scenario)


@router.get("", response_model=list[ScenarioResponse])
async def list_scenarios(
    db: AsyncSession = Depends(get_db),
) -> list[ScenarioResponse]:
    """List all scenarios."""
    service = ScenarioService(db)
    scenarios = await service.get_all_scenarios()
    return [ScenarioResponse.model_validate(s) for s in scenarios]


@router.post("/{scenario_name}/activate")
async def activate_scenario(
    scenario_name: str,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Activate a scenario."""
    service = ScenarioService(db)
    return await service.activate_scenario(name=scenario_name)
