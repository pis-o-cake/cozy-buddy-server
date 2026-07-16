"""auth 도메인 DB 접근."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.auth.models import Hub


async def get_hub_by_hub_id(session: AsyncSession, hub_id: str) -> Hub | None:
    return await session.scalar(sa.select(Hub).where(Hub.hub_id == hub_id))


async def get_hub_by_token_hash(session: AsyncSession, token_hash: str) -> Hub | None:
    return await session.scalar(sa.select(Hub).where(Hub.token_hash == token_hash))


async def create_hub(session: AsyncSession, *, hub_id: str, name: str, token_hash: str) -> Hub:
    hub = Hub(hub_id=hub_id, name=name, token_hash=token_hash)
    session.add(hub)
    await session.commit()
    await session.refresh(hub)
    return hub


async def delete_hub(session: AsyncSession, hub: Hub) -> None:
    await session.delete(hub)
    await session.commit()
