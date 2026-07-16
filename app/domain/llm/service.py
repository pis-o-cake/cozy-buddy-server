"""LLM Orchestrator (설계서 §7).

- system prompt 조립(§7-1): 안정 접두부(페르소나·스타일·tool 정책·기기 목록) 먼저,
  변동 정보(요약·발화 위치·시각)는 말미 — 프리픽스 캐시 훼손 최소화.
- tool loop(§7-3): 결과는 `role:"tool"` + tool_call_id 표준 주입, 마지막 턴 자체를
  스트리밍(재호출식 이중 생성 금지), 최대 5회.
"""

import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime

from loguru import logger

from app.config import get_settings
from app.core.i18n import t
from app.domain.llm.providers.base import (
    Done,
    GenOptions,
    LLMProvider,
    Message,
    ReasoningDelta,
    TextDelta,
    ToolCall,
    ToolCallDelta,
)
from app.domain.llm.tools.registry import ToolContext, ToolRegistry, tool_registry

MAX_TOOL_ITERATIONS = 5  # §7-3

_WEEKDAYS_KO = ("월", "화", "수", "목", "금", "토", "일")


@dataclass
class HubContext:
    hub_id: str
    room: str | None = None  # room slug/이름 — 미배정이면 None


@dataclass
class OrchTextDelta:
    text: str


@dataclass
class OrchToolStatus:
    tool: str
    status: str  # running | ok | failed  (§5-1 tool.status)


@dataclass
class OrchDone:
    text: str
    finish_reason: str
    new_messages: list[Message] = field(default_factory=list)  # 세션 저장용 (§7-4)


OrchEvent = OrchTextDelta | OrchToolStatus | OrchDone


def build_system_prompt(
    hub: HubContext, *, devices_block: str | None = None, summary: str | None = None
) -> str:
    """§7-1 블록 순서대로 system prompt를 조립한다."""
    blocks = [
        t("prompt.persona"),
        t("prompt.style"),
        t("prompt.tool_policy"),
        devices_block or t("prompt.no_devices"),  # Phase 2에서 device 도메인이 주입
    ]
    if summary:
        blocks.append(f"{t('prompt.summary_prefix')}: {summary}")
    if hub.room:
        blocks.append(t("prompt.room_context", room=hub.room))
    now = datetime.now()
    weekday = _WEEKDAYS_KO[now.weekday()]
    blocks.append(f"현재 시각: {now.year}년 {now.month}월 {now.day}일 ({weekday}) {now:%H:%M}")
    return "\n\n".join(blocks)


class Orchestrator:
    """대화 1턴을 실행한다: LLM 스트림 + tool loop + 이벤트 방출."""

    def __init__(self, provider: LLMProvider, tools: ToolRegistry | None = None) -> None:
        self._provider = provider
        self._tools = tools if tools is not None else tool_registry

    async def run_turn(
        self,
        history: list[Message],
        hub: HubContext,
        *,
        summary: str | None = None,
        devices_block: str | None = None,
        request_id: str | None = None,
    ) -> AsyncIterator[OrchEvent]:
        """history(마지막이 사용자 발화) 기준으로 응답을 스트리밍한다.

        Yields:
            OrchTextDelta(자막 스트리밍) / OrchToolStatus / OrchDone(최종 — 반드시 마지막).
        """
        settings = get_settings()
        system_prompt = build_system_prompt(hub, devices_block=devices_block, summary=summary)
        messages = [Message(role="system", content=system_prompt), *history]
        tool_ctx = ToolContext(hub_id=hub.hub_id, room=hub.room)
        new_messages: list[Message] = []
        full_text: list[str] = []

        for iteration in range(MAX_TOOL_ITERATIONS):
            turn_text: list[str] = []
            tool_calls_acc: dict[int, dict[str, str]] = {}
            finish_reason = "stop"

            stream = self._provider.chat_stream(
                messages,
                tools=self._tools.schemas() or None,
                options=GenOptions(request_id=request_id),
            )
            # LLM 타임아웃(§12-1): 첫 델타까지만 감시 — 이후는 스트림 자체가 진행 신호
            try:
                first = await asyncio.wait_for(
                    anext(stream), timeout=settings.llm_first_token_timeout_seconds
                )
            except (TimeoutError, StopAsyncIteration):
                logger.warning("llm first token timeout (iteration={})", iteration)
                yield OrchDone(text=t("voice.llm_timeout"), finish_reason="timeout")
                return

            async for delta in _prepend(first, stream):
                match delta:
                    case TextDelta(text=text):
                        turn_text.append(text)
                        yield OrchTextDelta(text=text)
                    case ReasoningDelta():
                        pass  # thinking은 자막·TTS 금지 채널 (§7-3)
                    case ToolCallDelta(index=index, id=tc_id, name=name, arguments=args):
                        empty = {"id": "", "name": "", "arguments": ""}
                        acc = tool_calls_acc.setdefault(index, dict(empty))
                        if tc_id:
                            acc["id"] = tc_id
                        if name:
                            acc["name"] = name
                        acc["arguments"] += args
                    case Done(finish_reason=reason):
                        finish_reason = reason

            full_text.extend(turn_text)

            if finish_reason != "tool_calls" or not tool_calls_acc:
                # 마지막 턴 — 이 스트림의 텍스트가 곧 사용자 응답 (§7-3 이중 생성 금지)
                assistant = Message(role="assistant", content="".join(full_text))
                new_messages.append(assistant)
                yield OrchDone(
                    text="".join(full_text), finish_reason=finish_reason, new_messages=new_messages
                )
                return

            # 툴콜 턴: assistant(tool_calls) 기록 → 실행 → role:"tool" 주입 (§7-3)
            calls = [
                ToolCall(
                    id=acc["id"] or f"call_{index}",
                    name=acc["name"],
                    arguments=acc["arguments"],
                )
                for index, acc in sorted(tool_calls_acc.items())
            ]
            assistant = Message(role="assistant", content="".join(turn_text), tool_calls=calls)
            messages.append(assistant)
            new_messages.append(assistant)

            for call in calls:
                yield OrchToolStatus(tool=call.name, status="running")
                result = await self._tools.execute(call.name, call.arguments, tool_ctx)
                yield OrchToolStatus(tool=call.name, status="ok" if result.ok else "failed")
                tool_message = Message(role="tool", content=result.content, tool_call_id=call.id)
                messages.append(tool_message)
                new_messages.append(tool_message)

        # 루프 초과(§7-3): 중단 + 부분 결과 안내
        logger.warning("tool loop exceeded {} iterations", MAX_TOOL_ITERATIONS)
        text = t("voice.tool_loop_exceeded")
        new_messages.append(Message(role="assistant", content=text))
        yield OrchDone(text=text, finish_reason="tool_loop_exceeded", new_messages=new_messages)


async def _prepend(first, rest):
    """이미 꺼낸 첫 델타를 스트림 앞에 되붙인다."""
    yield first
    async for item in rest:
        yield item
