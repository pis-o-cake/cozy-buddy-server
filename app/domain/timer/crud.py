"""timer 도메인 DB 접근."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.timer.models import Timer


async def list_timers(session: AsyncSession, hub_pk: int | None = None) -> list[Timer]:
    query = sa.select(Timer).order_by(Timer.fires_at)
    if hub_pk is not None:
        query = query.where(Timer.hub_id == hub_pk)
    return list((await session.scalars(query)).all())


async def get_timer(session: AsyncSession, timer_id: int) -> Timer | None:
    return await session.get(Timer, timer_id)


async def get_by_label(session: AsyncSession, hub_pk: int, label: str) -> Timer | None:
    return await session.scalar(
        sa.select(Timer).where(Timer.hub_id == hub_pk, Timer.label == label)
    )


async def create_timer(session: AsyncSession, **fields) -> Timer:
    timer = Timer(**fields)
    session.add(timer)
    await session.commit()
    await session.refresh(timer)
    return timer


async def delete_timer(session: AsyncSession, timer: Timer) -> None:
    await session.delete(timer)
    await session.commit()
