"""Tapo device adapter (python-kasa)."""

from typing import Any

from loguru import logger

from app.core.exceptions import DeviceError, DeviceOfflineError
from app.domain.device.adapters.base import DeviceAdapter


class TapoAdapter(DeviceAdapter):
    """TP-Link Tapo device adapter."""

    def __init__(self) -> None:
        self._device: Any = None
        self._host: str = ""

    async def connect(self, config: dict[str, Any]) -> None:
        """Connect to Tapo device."""
        # TODO: integrate python-kasa
        self._host = config.get("host", "")
        logger.info(f"Tapo device connected: {self._host}")

    async def disconnect(self) -> None:
        """Disconnect from device."""
        self._device = None

    async def turn_on(self) -> dict[str, Any]:
        """Turn on device."""
        if not self._host:
            raise DeviceOfflineError(device_name=self._host)
        # TODO: integrate python-kasa control
        logger.info(f"Tapo ON: {self._host}")
        return {"status": "on", "host": self._host}

    async def turn_off(self) -> dict[str, Any]:
        """Turn off device."""
        if not self._host:
            raise DeviceOfflineError(device_name=self._host)
        # TODO: integrate python-kasa control
        logger.info(f"Tapo OFF: {self._host}")
        return {"status": "off", "host": self._host}

    async def get_status(self) -> dict[str, Any]:
        """Get device status."""
        if not self._host:
            raise DeviceOfflineError(device_name=self._host)
        # TODO: integrate python-kasa status query
        return {"host": self._host, "is_on": False}

    async def execute(self, action: str, value: Any = None) -> dict[str, Any]:
        """Execute generic action."""
        match action:
            case "on":
                return await self.turn_on()
            case "off":
                return await self.turn_off()
            case "status":
                return await self.get_status()
            case _:
                raise DeviceError(
                    message=f"Unsupported action: {action}",
                    device_name=self._host,
                )
