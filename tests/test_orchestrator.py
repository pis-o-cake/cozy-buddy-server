"""Orchestrator tool loop (설계서 §7-3)."""

import json

from app.domain.llm.providers.base import Done, ReasoningDelta, TextDelta, ToolCallDelta, ToolSchema
from app.domain.llm.service import (
    HubContext,
    OrchDone,
    Orchestrator,
    OrchTextDelta,
    OrchToolStatus,
)
from app.domain.llm.tools.registry import ToolRegistry
from tests.fakes import FakeLLM

_HUB = HubContext(hub_id="test-01", room="living")


def _tool_registry_with_echo() -> tuple[ToolRegistry, list[dict]]:
    calls: list[dict] = []

    async def handler(arguments: dict, ctx) -> str:
        calls.append(arguments)
        return json.dumps({"ok": True})

    registry = ToolRegistry()
    registry.register(
        ToolSchema(name="control_device", description="기기 제어", parameters={"type": "object"}),
        handler,
    )
    return registry, calls


async def _collect(events):
    collected = []
    async for event in events:
        collected.append(event)
    return collected


async def test_tool_loop_executes_and_streams_final_turn():
    registry, calls = _tool_registry_with_echo()
    llm = FakeLLM(
        scripts=[
            # 1차: 툴콜 (arguments가 조각으로 분할 도착)
            [
                ToolCallDelta(index=0, id="call_1", name="control_device", arguments='{"device":'),
                ToolCallDelta(index=0, arguments=' "거실 조명", "value": "off"}'),
                Done(finish_reason="tool_calls"),
            ],
            # 2차: 최종 응답 스트리밍
            [TextDelta(text="거실 조명을 "), TextDelta(text="껐어요."), Done(finish_reason="stop")],
        ]
    )
    events = await _collect(Orchestrator(llm, registry).run_turn([], _HUB))

    assert calls == [{"device": "거실 조명", "value": "off"}]
    statuses = [e for e in events if isinstance(e, OrchToolStatus)]
    assert [s.status for s in statuses] == ["running", "ok"]

    done = events[-1]
    assert isinstance(done, OrchDone)
    assert done.text == "거실 조명을 껐어요."
    assert done.finish_reason == "stop"
    # §7-3: assistant(tool_calls) → role:"tool" → assistant(최종) 순으로 기록
    assert [m.role for m in done.new_messages] == ["assistant", "tool", "assistant"]
    assert done.new_messages[1].tool_call_id == "call_1"

    # 2차 호출에 role:"tool" 표준 주입 확인
    second_call_messages = llm.received[1]
    assert second_call_messages[-1].role == "tool"
    assert second_call_messages[-2].tool_calls is not None


async def test_reasoning_deltas_are_not_exposed():
    llm = FakeLLM(
        scripts=[
            [
                ReasoningDelta(text="비밀 사고 과정"),
                TextDelta(text="답변이에요."),
                Done(finish_reason="stop"),
            ]
        ]
    )
    events = await _collect(Orchestrator(llm, ToolRegistry()).run_turn([], _HUB))
    text_deltas = [e.text for e in events if isinstance(e, OrchTextDelta)]
    assert text_deltas == ["답변이에요."]


async def test_tool_loop_exceeded_returns_partial_notice():
    registry, calls = _tool_registry_with_echo()
    llm = FakeLLM(
        scripts=[
            [
                ToolCallDelta(index=0, id="c", name="control_device", arguments="{}"),
                Done(finish_reason="tool_calls"),
            ]
        ]  # 모든 호출이 툴콜 → 루프 상한 도달
    )
    events = await _collect(Orchestrator(llm, registry).run_turn([], _HUB))
    done = events[-1]
    assert isinstance(done, OrchDone)
    assert done.finish_reason == "tool_loop_exceeded"
    assert len(calls) == 5  # MAX_TOOL_ITERATIONS


async def test_first_token_timeout_falls_back(monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("LLM_FIRST_TOKEN_TIMEOUT_SECONDS", "0.05")
    get_settings.cache_clear()
    try:
        llm = FakeLLM(first_delta_delay=0.5)
        events = await _collect(Orchestrator(llm, ToolRegistry()).run_turn([], _HUB))
        done = events[-1]
        assert isinstance(done, OrchDone)
        assert done.finish_reason == "timeout"
        assert done.text  # 폴백 문구 (i18n)
    finally:
        get_settings.cache_clear()


async def test_system_prompt_contains_context_blocks():
    llm = FakeLLM()
    await _collect(
        Orchestrator(llm, ToolRegistry()).run_turn([], _HUB, summary="어제 조명 색을 바꿨음")
    )
    system = llm.received[0][0]
    assert system.role == "system"
    assert "Cozy Buddy" in system.content
    assert "living" in system.content
    assert "어제 조명 색을 바꿨음" in system.content
