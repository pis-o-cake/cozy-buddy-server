"""Device adapter abstract base."""

from abc import ABC, abstractmethod
from typing import Any


class DeviceAdapter(ABC):
    """IoT device adapter interface."""

    @abstractmethod
    async def connect(self, config: dict[str, Any]) -> None:
        """Connect to device."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from device."""

    @abstractmethod
    async def turn_on(self) -> dict[str, Any]:
        """Turn on device."""

    @abstractmethod
    async def turn_off(self) -> dict[str, Any]:
        """Turn off device."""

    @abstractmethod
    async def get_status(self) -> dict[str, Any]:
        """Get device status."""

    @abstractmethod
    async def execute(self, action: str, value: Any = None) -> dict[str, Any]:
        """Execute generic action."""
