"""Device domain API router."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.domain.device.schemas import (
    DeviceControlRequest,
    DeviceCreate,
    DeviceResponse,
)
from app.domain.device.service import DeviceService

router = APIRouter()


@router.post("", response_model=DeviceResponse)
async def register_device(
    request: DeviceCreate,
    db: AsyncSession = Depends(get_db),
) -> DeviceResponse:
    """Register a device."""
    service = DeviceService(db)
    device = await service.register_device(**request.model_dump())
    return DeviceResponse.model_validate(device)


@router.get("", response_model=list[DeviceResponse])
async def list_devices(
    db: AsyncSession = Depends(get_db),
) -> list[DeviceResponse]:
    """List all devices."""
    service = DeviceService(db)
    devices = await service.get_all_devices()
    return [DeviceResponse.model_validate(d) for d in devices]


@router.post("/{device_name}/control")
async def control_device(
    device_name: str,
    request: DeviceControlRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Control a device."""
    service = DeviceService(db)
    return await service.control_device(
        device_name=device_name, action=request.action, value=request.value
    )
