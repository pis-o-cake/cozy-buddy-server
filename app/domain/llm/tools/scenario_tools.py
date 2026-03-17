"""Scenario tools (Tool Calling)."""

from typing import Any

from app.domain.llm.tools.registry import ToolRegistry


@ToolRegistry.register(
    "activate_scenario",
    description="사전 정의된 시나리오를 실행합니다 (예: 영화 모드, 취침 모드)",
    parameters={
        "type": "object",
        "properties": {
            "scenario_name": {"type": "string", "description": "시나리오 이름"},
        },
        "required": ["scenario_name"],
    },
)
async def activate_scenario(scenario_name: str) -> dict[str, Any]:
    """Scenario activation tool."""
    from app.core.database import async_session
    from app.domain.scenario.service import ScenarioService

    async with async_session() as db:
        service = ScenarioService(db)
        return await service.activate_scenario(name=scenario_name)
