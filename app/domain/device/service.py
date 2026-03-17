"""Device domain service."""

from typing import Any

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DeviceError
from app.domain.device import crud
from app.domain.device.adapters.base import DeviceAdapter
from app.domain.device.adapters.tapo import TapoAdapter
from app.domain.device.models import Device


_ADAPTER_MAP: dict[str, type[DeviceAdapter]] = {
    "tapo": TapoAdapter,
}


class DeviceService:
    """IoT device control service."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def register_device(self, **kwargs: Any) -> Device:
        """Register a device."""
        return await crud.create_device(self._db, **kwargs)

    async def get_all_devices(self) -> list[Device]:
        """Get all devices."""
        return await crud.get_all_devices(self._db)

    async def control_device(
        self, *, device_name: str, action: str, value: Any = None
    ) -> dict[str, Any]:
        """Control a device."""
        device = await crud.get_device_by_name(self._db, name=device_name)
        if not device:
            raise DeviceError(message=f"Device not found: {device_name}")

        adapter_cls = _ADAPTER_MAP.get(device.adapter_type)
        if not adapter_cls:
            raise DeviceError(
                message=f"Unsupported adapter: {device.adapter_type}"
            )

        adapter = adapter_cls()
        await adapter.connect(device.config)

        try:
            result = await adapter.execute(action, value)
            logger.info(f"Device controlled: {device_name} -> {action}")
            return result
        finally:
            await adapter.disconnect()
