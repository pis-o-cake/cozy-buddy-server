"""chat 도메인 DB 접근."""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat.models import ChatSession, Message


async def get_latest_session(session: AsyncSession, hub_pk: int) -> ChatSession | None:
    return await session.scalar(
        sa.select(ChatSession)
        .where(ChatSession.hub_id == hub_pk)
        .order_by(ChatSession.id.desc())
        .limit(1)
    )


async def create_session(session: AsyncSession, hub_pk: int, now: datetime) -> ChatSession:
    chat_session = ChatSession(hub_id=hub_pk, last_active_at=now, created_at=now)
    session.add(chat_session)
    await session.commit()
    await session.refresh(chat_session)
    return chat_session


async def get_recent_messages(
    session: AsyncSession, session_pk: int, limit: int
) -> list[Message]:
    rows = (
        await session.scalars(
            sa.select(Message)
            .where(Message.session_id == session_pk)
            .order_by(Message.id.desc())
            .limit(limit)
        )
    ).all()
    return list(reversed(rows))


async def count_messages(session: AsyncSession, session_pk: int) -> int:
    return (
        await session.scalar(
            sa.select(sa.func.count()).select_from(Message).where(Message.session_id == session_pk)
        )
    ) or 0
