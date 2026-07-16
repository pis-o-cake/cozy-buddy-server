"""timer 도메인 LLM tools — set_timer·cancel_timer (설계서 §7-2)."""

import json
from typing import Any

import sqlalchemy as sa

from app.core.database import get_session_factory
from app.core.exceptions import NotFoundError
from app.domain.auth.models import Hub
from app.domain.llm.providers.base import ToolSchema
from app.domain.llm.tools.registry import ToolContext, tool_registry
from app.domain.timer import service


def _dumps(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


async def _set_timer(arguments: dict[str, Any], ctx: ToolContext) -> str:
    async with get_session_factory()() as session:
        hub = await session.scalar(sa.select(Hub).where(Hub.hub_id == ctx.hub_id))
        if hub is None:
            return _dumps({"ok": False, "error": "calling hub not found"})
        try:
            fires_at = service.parse_fires_at(
                duration_sec=arguments.get("duration_sec"), at=arguments.get("at")
            )
            timer = await service.create_timer(
                session,
                hub_pk=hub.id,
                kind=str(arguments.get("kind", "timer")),
                fires_at=fires_at,
                label=arguments.get("label"),
            )
        except ValueError as exc:
            return _dumps({"ok": False, "error": str(exc)})
    return _dumps({"ok": True, "timer_id": timer.id, "fires_at": timer.fires_at.isoformat()})


async def _cancel_timer(arguments: dict[str, Any], ctx: ToolContext) -> str:
    async with get_session_factory()() as session:
        hub = await session.scalar(sa.select(Hub).where(Hub.hub_id == ctx.hub_id))
        if hub is None:
            return _dumps({"ok": False, "error": "calling hub not found"})
        try:
            timer = await service.cancel_timer(
                session,
                hub_pk=hub.id,
                timer_id=arguments.get("timer_id"),
                label=arguments.get("label"),
            )
        except NotFoundError:
            return _dumps({"ok": False, "error": "timer not found"})
    return _dumps({"ok": True, "cancelled": timer.id})


tool_registry.register(
    ToolSchema(
        name="set_timer",
        description="타이머/알람/리마인더 설정. 타이머는 duration_sec, 알람/리마인더는 at 사용.",
        parameters={
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["timer", "alarm", "reminder"]},
                "duration_sec": {"type": "integer", "description": "타이머용 — 지금부터 몇 초 뒤"},
                "at": {"type": "string", "description": "알람/리마인더용 — 'HH:MM' 또는 ISO8601"},
                "label": {"type": "string", "description": "이름표 (예: 라면, 회의)"},
            },
            "required": ["kind"],
        },
    ),
    _set_timer,
)

tool_registry.register(
    ToolSchema(
        name="cancel_timer",
        description="설정된 타이머/알람을 취소한다. label 또는 timer_id로 지정.",
        parameters={
            "type": "object",
            "properties": {
                "label": {"type": "string"},
                "timer_id": {"type": "integer"},
            },
        },
    ),
    _cancel_timer,
)
