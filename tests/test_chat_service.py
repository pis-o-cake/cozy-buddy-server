"""chat 세션 정책 — 3분 만료·컨텍스트 창·롤링 요약 (설계서 §7-4)."""

from datetime import timedelta

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.auth.models import Hub
from app.domain.chat import service as chat_service
from app.domain.chat.service import _now
from app.domain.llm.providers.base import Done, Message, TextDelta, ToolCall
from tests.fakes import FakeLLM


async def _make_hub(db) -> Hub:
    hub = Hub(hub_id="living-01", name="거실 허브", token_hash="x" * 64)
    db.add(hub)
    await db.commit()
    await db.refresh(hub)
    return hub


async def test_session_reused_within_idle_window(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        hub = await _make_hub(db)
        first = await chat_service.get_or_create_session(db, hub.id)
        second = await chat_service.get_or_create_session(db, hub.id)
        assert first.id == second.id


async def test_session_expires_after_idle(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        hub = await _make_hub(db)
        first = await chat_service.get_or_create_session(db, hub.id)
        first.last_active_at = _now() - timedelta(seconds=chat_service.SESSION_IDLE_SECONDS + 1)
        await db.commit()
        second = await chat_service.get_or_create_session(db, hub.id)
        assert second.id != first.id


async def test_context_roundtrip_preserves_tool_messages(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        hub = await _make_hub(db)
        chat_session = await chat_service.get_or_create_session(db, hub.id)
        await chat_service.append_messages(
            db,
            chat_session,
            [
                Message(role="user", content="불 꺼줘"),
                Message(
                    role="assistant",
                    content="",
                    tool_calls=[ToolCall(id="c1", name="control_device", arguments="{}")],
                ),
                Message(role="tool", content='{"ok": true}', tool_call_id="c1"),
                Message(role="assistant", content="껐어요."),
            ],
        )
        history, summary = await chat_service.load_context(db, chat_session)

    assert summary is None
    assert [m.role for m in history] == ["user", "assistant", "tool", "assistant"]
    assert history[1].tool_calls[0].name == "control_device"
    assert history[2].tool_call_id == "c1"


async def test_context_window_limits_messages(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        hub = await _make_hub(db)
        chat_session = await chat_service.get_or_create_session(db, hub.id)
        for i in range(30):
            await chat_service.append_messages(
                db, chat_session, [Message(role="user", content=f"메시지 {i}")]
            )
        history, _ = await chat_service.load_context(db, chat_session)

    assert len(history) == chat_service.CONTEXT_MESSAGE_LIMIT
    assert history[-1].content == "메시지 29"  # 최신이 마지막 (시간순)


async def test_rolling_summary_compresses_old_turns(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as db:
        hub = await _make_hub(db)
        chat_session = await chat_service.get_or_create_session(db, hub.id)
        for i in range(chat_service.SUMMARY_TRIGGER_COUNT + 5):
            await chat_service.append_messages(
                db, chat_session, [Message(role="user", content=f"메시지 {i}")]
            )
        llm = FakeLLM(
            scripts=[[TextDelta(text="사용자가 여러 요청을 했다."), Done(finish_reason="stop")]]
        )
        await chat_service.maybe_roll_summary(db, chat_session, llm)

        assert chat_session.summary == "사용자가 여러 요청을 했다."
        # 요약 프롬프트에 오래된 메시지가 들어갔는지 확인
        assert "메시지 0" in llm.received[0][1].content
