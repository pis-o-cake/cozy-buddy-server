"""hub 운영 API (설계서 §5-2 — /api/hubs). 페어링/토큰은 auth 도메인 소관(§11)."""

import sqlalchemy as sa
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.websocket import hub_manager
from app.domain.auth.models import Hub
from app.domain.device import crud as device_crud

PREFIX = "/api/hubs"
router = APIRouter(tags=["hub"])


class HubPatch(BaseModel):
    name: str | None = None
    room_id: int | None = None


class HubOut(BaseModel):
    id: int
    hub_id: str
    name: str
    room_id: int | None
    connected: bool


def _to_out(hub: Hub) -> HubOut:
    return HubOut(
        id=hub.id,
        hub_id=hub.hub_id,
        name=hub.name,
        room_id=hub.room_id,
        connected=hub.hub_id in hub_manager.connected_hub_ids(),
    )


@router.get("", response_model=list[HubOut])
async def list_hubs(session: AsyncSession = Depends(get_session)) -> list[HubOut]:
    hubs = (await session.scalars(sa.select(Hub).order_by(Hub.id))).all()
    return [_to_out(h) for h in hubs]


@router.patch("/{hub_id}", response_model=HubOut)
async def patch_hub(
    hub_id: str, body: HubPatch, session: AsyncSession = Depends(get_session)
) -> HubOut:
    """허브 이름/방 배정 (§8 멀티룸 — room-aware 해석의 기준이 된다)."""
    hub = await session.scalar(sa.select(Hub).where(Hub.hub_id == hub_id))
    if hub is None:
        raise NotFoundError(f"hub '{hub_id}' not found")
    if body.room_id is not None and await device_crud.get_room(session, body.room_id) is None:
        raise NotFoundError(f"room {body.room_id} not found")
    if body.name is not None:
        hub.name = body.name
    if body.room_id is not None:
        hub.room_id = body.room_id
    await session.commit()
    await session.refresh(hub)
    return _to_out(hub)
