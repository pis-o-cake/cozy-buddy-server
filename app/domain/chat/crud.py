"""Chat domain CRUD."""

from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.chat.models import Conversation


async def create_message(
    db: AsyncSession,
    *,
    role: str,
    content: str,
    tool_call: dict[str, Any] | None = None,
) -> Conversation:
    """Save a conversation message."""
    message = Conversation(role=role, content=content, tool_call=tool_call)
    db.add(message)
    await db.flush()
    return message


async def get_recent_messages(
    db: AsyncSession,
    *,
    limit: int = 20,
) -> list[Conversation]:
    """Get recent conversation messages."""
    stmt = (
        select(Conversation)
        .order_by(Conversation.id.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return list(reversed(result.scalars().all()))


async def get_message_count(db: AsyncSession) -> int:
    """Get total message count."""
    stmt = select(func.count(Conversation.id))
    result = await db.execute(stmt)
    return result.scalar_one()


async def clear_messages(db: AsyncSession) -> int:
    """Delete all messages. Returns deleted count."""
    count = await get_message_count(db)
    stmt = delete(Conversation)
    await db.execute(stmt)
    await db.flush()
    return count
