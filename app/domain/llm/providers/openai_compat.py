"""OpenAI 호환(chat/completions) 공통 베이스 어댑터.

gemini·openai·llamacpp가 base_url·인증만 달리해 이 구현을 공유한다 (설계서 §14-2 Phase 0).
SSE 파싱에서 tool_calls 델타를 1급으로 처리 — 텍스트만 뽑고 툴콜을 버리는 실수 금지
(기존 구현의 결함 체크리스트, 설계서 §14-1).
"""

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx
from loguru import logger

from app.domain.llm.providers.base import (
    ChatDelta,
    Done,
    GenOptions,
    LLMCapabilities,
    LLMProvider,
    Message,
    ProviderHealth,
    TextDelta,
    ToolCallDelta,
    ToolSchema,
    Usage,
)


def _to_openai_messages(messages: list[Message]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in messages:
        entry: dict[str, Any] = {"role": m.role, "content": m.content}
        if m.role == "assistant" and m.tool_calls:
            entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.name, "arguments": tc.arguments},
                }
                for tc in m.tool_calls
            ]
        if m.role == "tool":
            entry["tool_call_id"] = m.tool_call_id
        out.append(entry)
    return out


def _to_openai_tools(tools: list[ToolSchema]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {"name": t.name, "description": t.description, "parameters": t.parameters},
        }
        for t in tools
    ]


class OpenAICompatProvider(LLMProvider):
    """OpenAI 호환 엔드포인트 스트리밍 어댑터. 서브클래스는 name·기본 접속 정보만 지정."""

    def __init__(self, *, base_url: str, api_key: str, model: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._cancel_events: dict[str, asyncio.Event] = {}

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

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": _to_openai_messages(messages),
            "max_tokens": opts.max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if tools:
            payload["tools"] = _to_openai_tools(tools)

        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        finish_reason = "stop"
        usage = Usage()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
                async with client.stream(
                    "POST", f"{self._base_url}/chat/completions", json=payload, headers=headers
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if cancel_event.is_set():
                            finish_reason = "cancelled"
                            break
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            break
                        chunk = json.loads(data)
                        if chunk.get("usage"):
                            usage = Usage(
                                input_tokens=chunk["usage"].get("prompt_tokens", 0),
                                output_tokens=chunk["usage"].get("completion_tokens", 0),
                            )
                        choices = chunk.get("choices") or []
                        if not choices:
                            continue
                        choice = choices[0]
                        if choice.get("finish_reason"):
                            finish_reason = choice["finish_reason"]
                        delta = choice.get("delta") or {}
                        if delta.get("content"):
                            yield TextDelta(text=delta["content"])
                        for tc in delta.get("tool_calls") or []:
                            fn = tc.get("function") or {}
                            yield ToolCallDelta(
                                index=tc.get("index", 0),
                                id=tc.get("id"),
                                name=fn.get("name"),
                                arguments=fn.get("arguments") or "",
                            )
        finally:
            if opts.request_id:
                self._cancel_events.pop(opts.request_id, None)
        yield Done(finish_reason=finish_reason, usage=usage)

    async def health(self) -> ProviderHealth:
        headers = {"Authorization": f"Bearer {self._api_key}"} if self._api_key else {}
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self._base_url}/models", headers=headers)
            if response.status_code == 200:
                return ProviderHealth(ok=True)
            return ProviderHealth(ok=False, detail=f"HTTP {response.status_code}")
        except httpx.HTTPError as exc:
            logger.warning("llm health check failed ({}): {}", self.name, exc)
            return ProviderHealth(ok=False, detail=str(exc))

    def capabilities(self) -> LLMCapabilities:
        return LLMCapabilities(tools=True, json_schema=True)

    async def cancel(self, request_id: str) -> None:
        event = self._cancel_events.get(request_id)
        if event is None:
            return
        event.set()
        logger.info("llm request cancelled ({}): {}", self.name, request_id)
