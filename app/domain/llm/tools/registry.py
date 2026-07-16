"""LLM tool 레지스트리 (설계서 §7-2).

Phase 2에서 device/scenario/timer 도메인이 자기 tool을 여기에 등록한다 —
Orchestrator는 등록된 스키마 목록만 노출하고 이름으로 실행한다.
"""

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from app.domain.llm.providers.base import ToolSchema


@dataclass
class ToolContext:
    """tool 실행 시 주입되는 발화 컨텍스트 (room-aware 해석의 기준 — §8-3)."""

    hub_id: str = ""
    room: str | None = None


ToolHandler = Callable[[dict[str, Any], ToolContext], Awaitable[str]]


@dataclass
class ToolResult:
    ok: bool
    content: str  # role:"tool" 메시지로 주입되는 문자열 (§7-3)


class ToolRegistry:
    def __init__(self) -> None:
        self._schemas: dict[str, ToolSchema] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, schema: ToolSchema, handler: ToolHandler) -> None:
        if schema.name in self._schemas:
            raise ValueError(f"tool '{schema.name}' already registered")
        self._schemas[schema.name] = schema
        self._handlers[schema.name] = handler

    def unregister(self, name: str) -> None:
        self._schemas.pop(name, None)
        self._handlers.pop(name, None)

    def schemas(self) -> list[ToolSchema]:
        return list(self._schemas.values())

    async def execute(
        self, name: str, arguments_json: str, ctx: ToolContext | None = None
    ) -> ToolResult:
        """tool을 실행한다. 모든 실패는 모델이 읽는 오류 결과로 변환 (§7-3)."""
        handler = self._handlers.get(name)
        if handler is None:
            return ToolResult(ok=False, content=json.dumps({"error": f"unknown tool: {name}"}))
        try:
            arguments: dict[str, Any] = json.loads(arguments_json) if arguments_json else {}
        except json.JSONDecodeError as exc:
            return ToolResult(ok=False, content=json.dumps({"error": f"invalid arguments: {exc}"}))
        try:
            return ToolResult(ok=True, content=await handler(arguments, ctx or ToolContext()))
        except Exception as exc:  # tool 실패가 파이프라인을 죽이면 안 된다
            logger.exception("tool execution failed: {}", name)
            return ToolResult(ok=False, content=json.dumps({"error": str(exc)}))


tool_registry = ToolRegistry()
