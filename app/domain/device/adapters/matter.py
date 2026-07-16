"""Matter 어댑터 슬롯 — matterjs-server WS 클라이언트 (설계서 §8-1).

IMPORTANT: matterjs-server는 Linux host-network Docker(WSL2) 구동이 전제(§13-1)인데
현 개발 머신에 WSL2/Docker가 없어 실연동을 보류한 슬롯이다. 인터페이스 계약과
레지스트리 등록만 유지해, 서버 확보 시 이 파일만 구현하면 편입된다 (§3-2).
"""

from typing import ClassVar

from app.domain.device.adapters.base import (
    AdapterNotSupportedError,
    CommandResult,
    DeviceAdapter,
    DeviceCommand,
    DeviceState,
    DiscoveredDevice,
    adapter_registry,
)
from app.domain.device.models import Device

_NOT_READY = "matter adapter requires matterjs-server (WSL2 Docker) — not configured yet"


@adapter_registry.register("matter")
class MatterAdapter(DeviceAdapter):
    adapter_type: ClassVar[str] = "matter"

    async def discover(self) -> list[DiscoveredDevice]:
        raise AdapterNotSupportedError(_NOT_READY)

    async def commission(self, pairing_code: str) -> DiscoveredDevice:
        """QR/셋업코드 커미셔닝 (§8-2 — REST /api/devices/commission이 호출)."""
        raise AdapterNotSupportedError(_NOT_READY)

    async def identify(self, device: Device) -> None:
        raise AdapterNotSupportedError(_NOT_READY)

    async def get_state(self, device: Device) -> DeviceState:
        raise AdapterNotSupportedError(_NOT_READY)

    async def execute(self, device: Device, command: DeviceCommand) -> CommandResult:
        raise AdapterNotSupportedError(_NOT_READY)
