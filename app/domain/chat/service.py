"""chat 도메인 서비스 — hub_id 단위 세션·컨텍스트 (설계서 §7-4).

- 세션 키 = 허브. 3분 유휴 시 새 세션(컨텍스트 리셋, 이력은 DB 보존).
- 컨텍스트 = 롤링 요약 + 최근 N개 메시지 원문.
"""

from datetime import UTC, datetime

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import t
from app.domain.chat import crud
from app.domain.chat.models import ChatSession, Message
from app.domain.llm.providers.base import Done, GenOptions, LLMProvider, TextDelta, ToolCall
from app.domain.llm.providers.base import Message as LLMMessage

SESSION_IDLE_SECONDS = 180  # 3분 (§7-4)
CONTEXT_MESSAGE_LIMIT = 20  # 최근 10턴 상당 (user/assistant/tool 포함)
SUMMARY_TRIGGER_COUNT = 30  # 초과분 롤링 요약 트리거


def _now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def get_or_create_session(session: AsyncSession, hub_pk: int) -> ChatSession:
    """유휴 3분 이내면 기존 세션을 잇고, 아니면 새 세션을 연다."""
    latest = await crud.get_latest_session(session, hub_pk)
    now = _now()
    if latest is not None and (now - latest.last_active_at).total_seconds() < SESSION_IDLE_SECONDS:
        return latest
    return await crud.create_session(session, hub_pk, now)


async def load_context(
    session: AsyncSession, chat_session: ChatSession
) -> tuple[list[LLMMessage], str | None]:
    """LLM에 넣을 (최근 메시지, 롤링 요약)을 반환한다."""
    rows = await crud.get_recent_messages(session, chat_session.id, CONTEXT_MESSAGE_LIMIT)
    return [_row_to_llm(row) for row in rows], chat_session.summary


async def append_messages(
    session: AsyncSession, chat_session: ChatSession, messages: list[LLMMessage]
) -> None:
    """턴의 메시지들(user/assistant/tool — §7-4)을 저장하고 세션 활동 시각을 갱신한다."""
    for m in messages:
        if m.role == "tool":
            # tool 결과 행은 tool_call_id를 tool_calls 컬럼에 보존 → 컨텍스트 복원 시 재사용
            tool_calls = [{"id": m.tool_call_id, "name": "", "arguments": ""}]
        elif m.tool_calls:
            tool_calls = [
                {"id": tc.id, "name": tc.name, "arguments": tc.arguments} for tc in m.tool_calls
            ]
        else:
            tool_calls = None
        session.add(
            Message(
                session_id=chat_session.id, role=m.role, content=m.content, tool_calls=tool_calls
            )
        )
    chat_session.last_active_at = _now()
    await session.commit()


async def maybe_roll_summary(
    session: AsyncSession, chat_session: ChatSession, provider: LLMProvider
) -> None:
    """메시지가 임계치를 넘으면 오래된 구간을 요약해 summary에 접는다 (베스트에포트).

    응답 전송 후에 호출되므로 사용자 체감 지연에는 영향이 없다.
    """
    total = await crud.count_messages(session, chat_session.id)
    if total <= SUMMARY_TRIGGER_COUNT:
        return
    older = await crud.get_recent_messages(session, chat_session.id, total)
    target = older[:-CONTEXT_MESSAGE_LIMIT]
    if not target:
        return

    transcript = "\n".join(f"{m.role}: {m.content}" for m in target if m.content)
    prompt = [
        LLMMessage(role="system", content=t("prompt.summarize_request")),
        LLMMessage(role="user", content=transcript),
    ]
    try:
        chunks: list[str] = []
        async for delta in provider.chat_stream(prompt, options=GenOptions(max_tokens=300)):
            if isinstance(delta, TextDelta):
                chunks.append(delta.text)
            elif isinstance(delta, Done):
                break
        summary = "".join(chunks).strip()
        if not summary:
            return
        prefix = f"{chat_session.summary} / " if chat_session.summary else ""
        chat_session.summary = f"{prefix}{summary}"[:2000]
        await session.commit()
        logger.info("chat session {} summary rolled ({} msgs)", chat_session.id, len(target))
    except Exception as exc:  # 요약 실패는 대화를 막지 않는다
        logger.warning("summary roll failed: {}", exc)


def _row_to_llm(row: Message) -> LLMMessage:
    if row.role == "tool":
        tool_call_id = row.tool_calls[0].get("id") if row.tool_calls else None
        return LLMMessage(role="tool", content=row.content, tool_call_id=tool_call_id)
    tool_calls = None
    if row.tool_calls:
        tool_calls = [
            ToolCall(id=tc["id"], name=tc["name"], arguments=tc["arguments"])
            for tc in row.tool_calls
        ]
    return LLMMessage(role=row.role, content=row.content, tool_calls=tool_calls)
