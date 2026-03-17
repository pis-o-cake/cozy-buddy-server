"""Device domain CRUD."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.device.models import Device


async def create_device(
    db: AsyncSession,
    *,
    name: str,
    device_type: str,
    adapter_type: str,
    location: str,
    config: dict[str, Any] | None = None,
) -> Device:
    """Register a device."""
    device = Device(
        name=name,
        device_type=device_type,
        adapter_type=adapter_type,
        location=location,
        config=config or {},
    )
    db.add(device)
    await db.flush()
    return device


async def get_device_by_name(db: AsyncSession, *, name: str) -> Device | None:
    """Get device by name."""
    stmt = select(Device).where(Device.name == name)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_devices(db: AsyncSession, *, active_only: bool = True) -> list[Device]:
    """Get all devices."""
    stmt = select(Device)
    if active_only:
        stmt = stmt.where(Device.is_active.is_(True))
    result = await db.execute(stmt)
    return list(result.scalars().all())
