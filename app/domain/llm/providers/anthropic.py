"""Anthropic(Claude) 어댑터 — 공식 SDK 사용 (OpenAI 호환 레이어 대신 네이티브 API).

Claude의 tool_use/thinking 블록 이벤트를 ChatDelta로 매핑한다.
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any, ClassVar

from anthropic import NOT_GIVEN, AsyncAnthropic
from loguru import logger

from app.config import Settings
from app.core.exceptions import ProviderNotConfiguredError
from app.domain.llm.providers.base import (
    ChatDelta,
    Done,
    GenOptions,
    LLMCapabilities,
    LLMProvider,
    Message,
    ProviderHealth,
    ReasoningDelta,
    TextDelta,
    ToolCallDelta,
    ToolSchema,
    Usage,
)
from app.domain.llm.providers.registry import llm_registry

_DEFAULT_MODEL = "claude-opus-4-8"

_FINISH_REASON_MAP = {
    "end_turn": "stop",
    "tool_use": "tool_calls",
    "max_tokens": "length",
}


def _split_system(messages: list[Message]) -> tuple[str, list[Message]]:
    """system 롤을 분리한다 — Anthropic API는 system이 별도 파라미터."""
    system_parts = [m.content for m in messages if m.role == "system"]
    rest = [m for m in messages if m.role != "system"]
    return "\n\n".join(system_parts), rest


def _to_anthropic_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        if m.role == "tool":
            # tool 결과는 user 턴의 tool_result 블록으로 (연속 user는 API가 병합)
            out.append(
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": m.tool_call_id,
                            "content": m.content,
                        }
                    ],
                }
            )
            continue
        if m.role == "assistant" and m.tool_calls:
            blocks: list[dict[str, Any]] = []
            if m.content:
                blocks.append({"type": "text", "text": m.content})
            for tc in m.tool_calls:
                blocks.append(
                    {
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.name,
                        "input": json.loads(tc.arguments) if tc.arguments else {},
                    }
                )
            out.append({"role": "assistant", "content": blocks})
            continue
        out.append({"role": m.role, "content": m.content})
    return out


@llm_registry.register("anthropic")
class AnthropicProvider(LLMProvider):
    name: ClassVar[str] = "anthropic"

    def __init__(self, *, api_key: str, model: str) -> None:
        self._client = AsyncAnthropic(api_key=api_key)
        self._model = model
        self._cancel_events: dict[str, asyncio.Event] = {}

    @classmethod
    def from_settings(cls, settings: Settings) -> "AnthropicProvider":
        if not settings.anthropic_api_key:
            raise ProviderNotConfiguredError("ANTHROPIC_API_KEY is not set")
        return cls(api_key=settings.anthropic_api_key, model=settings.llm_model or _DEFAULT_MODEL)

    async def chat_stream(
        self,
        messages: list[Message],
        *,
        tools: list[ToolSchema] | None = None,
        options: GenOptions | None = None,
    ) -> AsyncIterator[ChatDelta]:
        opts = options or GenOptions()
        cancel_event = asyncio.Event()
        if opts.request_id:
            self._cancel_events[opts.request_id] = cancel_event

        system_text, rest = _split_system(messages)
        anthropic_tools = NOT_GIVEN
        if tools:
            anthropic_tools = [
                {"name": t.name, "description": t.description, "input_schema": t.parameters}
                for t in tools
            ]

        finish_reason = "stop"
        usage = Usage()
        # content_block index → tool 여부 (input_json_delta 라우팅용)
        tool_block_indexes: set[int] = set()
        try:
            stream = await self._client.messages.create(
                model=self._model,
                max_tokens=opts.max_tokens,
                system=system_text or NOT_GIVEN,
                messages=_to_anthropic_messages(rest),
                tools=anthropic_tools,
                stream=True,
            )
            async for event in stream:
                if cancel_event.is_set():
                    finish_reason = "cancelled"
                    await stream.close()
                    break
                if event.type == "message_start":
                    usage.input_tokens = event.message.usage.input_tokens
                elif event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        tool_block_indexes.add(event.index)
                        yield ToolCallDelta(index=event.index, id=block.id, name=block.name)
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        yield TextDelta(text=delta.text)
                    elif delta.type == "thinking_delta":
                        yield ReasoningDelta(text=delta.thinking)
                    elif delta.type == "input_json_delta" and event.index in tool_block_indexes:
                        yield ToolCallDelta(index=event.index, arguments=delta.partial_json)
                elif event.type == "message_delta":
                    stop_reason = event.delta.stop_reason
                    if stop_reason:
                        finish_reason = _FINISH_REASON_MAP.get(stop_reason, stop_reason)
                    if event.usage:
                        usage.output_tokens = event.usage.output_tokens
        finally:
            if opts.request_id:
                self._cancel_events.pop(opts.request_id, None)
        yield Done(finish_reason=finish_reason, usage=usage)

    async def health(self) -> ProviderHealth:
        try:
            await self._client.models.retrieve(self._model)
            return ProviderHealth(ok=True)
        except Exception as exc:  # SDK 예외 계층 전체를 가용성 실패로 취급
            logger.warning("llm health check failed (anthropic): {}", exc)
            return ProviderHealth(ok=False, detail=str(exc))

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(tools=True, json_schema=True, vision=True, reasoning=True)

    async def cancel(self, request_id: str) -> None:
        event = self._cancel_events.get(request_id)
        if event is None:
            return
        event.set()
        logger.info("llm request cancelled (anthropic): {}", request_id)
