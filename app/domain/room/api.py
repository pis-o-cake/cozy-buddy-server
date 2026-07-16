"""room API (설계서 §5-2 — /api/rooms). Room 모델은 device 도메인 소유(§6-1)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import ConflictError, NotFoundError
from app.domain.device import crud
from app.domain.device.schemas import RoomCreate, RoomOut

PREFIX = "/api/rooms"
router = APIRouter(tags=["room"])


@router.get("", response_model=list[RoomOut])
async def list_rooms(session: AsyncSession = Depends(get_session)) -> list[RoomOut]:
    return [RoomOut.model_validate(r) for r in await crud.list_rooms(session)]


@router.post("", response_model=RoomOut)
async def create_room(body: RoomCreate, session: AsyncSession = Depends(get_session)) -> RoomOut:
    if await crud.get_room_by_slug(session, body.slug) is not None:
        raise ConflictError(f"room slug '{body.slug}' already exists")
    room = await crud.create_room(session, name=body.name, slug=body.slug)
    return RoomOut.model_validate(room)


@router.delete("/{room_id}", status_code=204)
async def delete_room(room_id: int, session: AsyncSession = Depends(get_session)) -> None:
    room = await crud.get_room(session, room_id)
    if room is None:
        raise NotFoundError(f"room {room_id} not found")
    await crud.delete_room(session, room)
