"""DeviceAdapter 계약 (설계서 §3-2 · §8-1).

브랜드/프로토콜별 어댑터가 이 계약만 구현하면 편입된다. 검색·물리 식별(identify)·
상태 조회·명령 실행·상태 push를 담당하고, 재시도 등 실패 정책은 상위 서비스 소관.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar

from app.core.registry import ProviderRegistry

if TYPE_CHECKING:
    from app.domain.device.models import Device


@dataclass
class DiscoveredDevice:
    """LAN 스캔 결과 — 등록 플로우(§8-2)의 후보."""

    adapter_type: str
    name: str
    model: str
    config: dict[str, Any]  # 등록 시 Device.config로 저장 (host 등)
    suggested_type: str = "plug"  # taxonomy 추정값 (사용자가 등록 시 확정)


@dataclass
class DeviceState:
    online: bool
    attributes: dict[str, Any] = field(default_factory=dict)  # capability → 현재값


@dataclass
class DeviceCommand:
    capability: str  # taxonomy 쓰기 capability (§8-1)
    value: Any


@dataclass
class CommandResult:
    ok: bool
    detail: str = ""


class AdapterNotSupportedError(RuntimeError):
    """어댑터가 해당 기능/환경을 지원하지 않음 — 어댑터별 장애 격리 (§12-1)."""


class DeviceAdapter(ABC):
    adapter_type: ClassVar[str] = ""

    @abstractmethod
    async def discover(self) -> list[DiscoveredDevice]:
        """LAN에서 등록 후보를 검색한다."""

    @abstractmethod
    async def identify(self, device: "Device") -> None:
        """기기 깜빡임/토글로 물리 식별 — 등록 '연결 확인' 단계 (§8-2)."""

    @abstractmethod
    async def get_state(self, device: "Device") -> DeviceState: ...

    @abstractmethod
    async def execute(self, device: "Device", command: DeviceCommand) -> CommandResult: ...

    async def subscribe(self, device: "Device") -> AsyncIterator[DeviceState]:
        """상태 push 스트림 — 폴링 어댑터는 기본 미지원 (HA/MQTT 어댑터가 override)."""
        raise AdapterNotSupportedError(f"{self.adapter_type} does not support subscribe")
        yield  # pragma: no cover — AsyncIterator 시그니처용


adapter_registry: ProviderRegistry[DeviceAdapter] = ProviderRegistry("device-adapter")
