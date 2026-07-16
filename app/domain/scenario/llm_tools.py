"""scenario 도메인 LLM tool — run_scenario (설계서 §7-2)."""

import json
from typing import Any

from app.core.database import get_session_factory
from app.domain.llm.providers.base import ToolSchema
from app.domain.llm.tools.registry import ToolContext, tool_registry
from app.domain.scenario import crud, service


async def _run_scenario(arguments: dict[str, Any], ctx: ToolContext) -> str:
    name = str(arguments.get("name", "")).strip()
    async with get_session_factory()() as session:
        scenario = await crud.get_by_name(session, name)
        if scenario is None or not scenario.enabled:
            return json.dumps(
                {"ok": False, "error": f"scenario '{name}' not found"}, ensure_ascii=False
            )
        run = await service.execute_scenario(session, scenario)
    return json.dumps(
        {
            "ok": run.ok,
            "scenario": name,
            "failed": [r.model_dump() for r in run.results if not r.ok],  # 부분 실패 보고 (§12-1)
        },
        ensure_ascii=False,
    )


tool_registry.register(
    ToolSchema(
        name="run_scenario",
        description="저장된 시나리오(루틴)를 이름으로 실행한다. 예: 굿모닝, 굿나잇.",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "시나리오 이름"}},
            "required": ["name"],
        },
    ),
    _run_scenario,
)
