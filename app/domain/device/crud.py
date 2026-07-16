"""device 도메인 DB 접근 (Room 포함 — Room 모델은 이 도메인 소유)."""

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.device.models import Device, Room


async def list_rooms(session: AsyncSession) -> list[Room]:
    return list((await session.scalars(sa.select(Room).order_by(Room.id))).all())


async def get_room(session: AsyncSession, room_id: int) -> Room | None:
    return await session.get(Room, room_id)


async def get_room_by_slug(session: AsyncSession, slug: str) -> Room | None:
    return await session.scalar(sa.select(Room).where(Room.slug == slug))


async def create_room(session: AsyncSession, *, name: str, slug: str) -> Room:
    room = Room(name=name, slug=slug)
    session.add(room)
    await session.commit()
    await session.refresh(room)
    return room


async def delete_room(session: AsyncSession, room: Room) -> None:
    await session.delete(room)
    await session.commit()


async def list_devices(session: AsyncSession) -> list[Device]:
    return list((await session.scalars(sa.select(Device).order_by(Device.id))).all())


async def get_device(session: AsyncSession, device_id: int) -> Device | None:
    return await session.get(Device, device_id)


async def create_device(session: AsyncSession, **fields) -> Device:
    device = Device(**fields)
    session.add(device)
    await session.commit()
    await session.refresh(device)
    return device


async def delete_device(session: AsyncSession, device: Device) -> None:
    await session.delete(device)
    await session.commit()
