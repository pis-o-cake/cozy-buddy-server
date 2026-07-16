"""timer API (설계서 §5-2 — /api/timers)."""

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.domain.auth.models import Hub
from app.domain.timer import crud, service
from app.domain.timer.schemas import TimerCreate, TimerOut

PREFIX = "/api/timers"
router = APIRouter(tags=["timer"])


@router.get("", response_model=list[TimerOut])
async def list_timers(session: AsyncSession = Depends(get_session)) -> list[TimerOut]:
    return [TimerOut.model_validate(t) for t in await crud.list_timers(session)]


@router.post("", response_model=TimerOut)
async def create_timer(body: TimerCreate, session: AsyncSession = Depends(get_session)) -> TimerOut:
    hub = await session.scalar(sa.select(Hub).where(Hub.hub_id == body.hub_id))
    if hub is None:
        raise NotFoundError(f"hub '{body.hub_id}' not found")
    fires_at = service.parse_fires_at(duration_sec=body.duration_sec, at=body.at)
    timer = await service.create_timer(
        session,
        hub_pk=hub.id,
        kind=body.kind,
        fires_at=fires_at,
        label=body.label,
        recurrence=body.recurrence,
        sunrise=body.sunrise,
    )
    return TimerOut.model_validate(timer)


@router.delete("/{timer_id}", status_code=204)
async def delete_timer(timer_id: int, session: AsyncSession = Depends(get_session)) -> None:
    timer = await crud.get_timer(session, timer_id)
    if timer is None:
        raise NotFoundError(f"timer {timer_id} not found")
    await service.cancel_timer(session, hub_pk=timer.hub_id, timer_id=timer_id)
