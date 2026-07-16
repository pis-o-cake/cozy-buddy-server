"""device 도메인 LLM tools — control_device·query_device (설계서 §7-2)."""

import json
from typing import Any

from app.core.database import get_session_factory
from app.core.exceptions import NotFoundError
from app.domain.device import service, taxonomy
from app.domain.device.service import AmbiguousDeviceError
from app.domain.llm.providers.base import ToolSchema
from app.domain.llm.tools.registry import ToolContext, tool_registry


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


async def _control_device(arguments: dict[str, Any], ctx: ToolContext) -> str:
    async with get_session_factory()() as session:
        try:
            result = await service.control_device(
                session,
                ref=str(arguments.get("device", "")),
                room=arguments.get("room"),
                hub_room=ctx.room,
                capability=str(arguments.get("capability", "")),
                value=arguments.get("value"),
            )
        except NotFoundError as exc:
            return _dumps({"ok": False, "error": str(exc)})
        except AmbiguousDeviceError as exc:
            # 후보를 알려 확인 질문을 유도한다 (§7-3 확인 질문 정책 ①)
            return _dumps({"ok": False, "ambiguous": exc.candidates, "error": "ask user which one"})
    return _dumps(result)


async def _query_device(arguments: dict[str, Any], ctx: ToolContext) -> str:
    async with get_session_factory()() as session:
        try:
            result = await service.query_device(
                session,
                ref=str(arguments.get("device", "")),
                room=arguments.get("room"),
                hub_room=ctx.room,
            )
        except NotFoundError as exc:
            return _dumps({"ok": False, "error": str(exc)})
        except AmbiguousDeviceError as exc:
            return _dumps({"ok": False, "ambiguous": exc.candidates, "error": "ask user which one"})
    return _dumps(result)


tool_registry.register(
    ToolSchema(
        name="control_device",
        description="스마트홈 기기를 제어한다. 방 미명시 시 발화 위치의 방에서 먼저 찾는다.",
        parameters={
            "type": "object",
            "properties": {
                "device": {
                    "type": "string",
                    "description": "기기 이름 또는 '거실 불' 같은 자연어 지칭",
                },
                "room": {
                    "type": "string",
                    "description": "명시된 방(slug/이름). 생략 시 발화 허브의 방",
                },
                "capability": {
                    "type": "string",
                    # taxonomy에서 동적 생성 — 하드코딩 금지 (§7-2)
                    "enum": taxonomy.writable_capabilities(),
                },
                "value": {"description": "on/off, 0-100, 2700-6500, 목표온도 등 capability별 값"},
            },
            "required": ["device", "capability", "value"],
        },
    ),
    _control_device,
)

tool_registry.register(
    ToolSchema(
        name="query_device",
        description="기기의 현재 상태(켜짐/밝기/온도 등)를 조회한다.",
        parameters={
            "type": "object",
            "properties": {
                "device": {"type": "string"},
                "room": {"type": "string"},
                "attribute": {"type": "string", "description": "관심 속성 (선택)"},
            },
            "required": ["device"],
        },
    ),
    _query_device,
)
