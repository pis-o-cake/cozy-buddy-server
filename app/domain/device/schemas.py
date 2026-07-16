"""device 도메인 요청/응답 스키마 (설계서 §5-2)."""

from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.domain.device import taxonomy


class RoomCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=50, pattern=r"^[a-z0-9\-]+$")


class RoomOut(BaseModel):
    id: int
    name: str
    slug: str

    model_config = {"from_attributes": True}


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    room_id: int
    device_type: str
    adapter_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    capabilities: list[str] | None = None  # 생략 시 taxonomy 기본 프로파일 (§8-1)

    @field_validator("device_type")
    @classmethod
    def _known_type(cls, value: str) -> str:
        if not taxonomy.is_known_type(value):
            raise ValueError(f"unknown device_type: {value}")
        return value


class DevicePatch(BaseModel):
    name: str | None = None
    room_id: int | None = None
    device_type: str | None = None
    capabilities: list[str] | None = None
    config: dict[str, Any] | None = None


class DeviceOut(BaseModel):
    id: int
    name: str
    room_id: int
    device_type: str
    adapter_type: str
    capabilities: list[str]
    online: bool

    model_config = {"from_attributes": True}


class CommandRequest(BaseModel):
    capability: str
    value: Any


class DiscoveredOut(BaseModel):
    adapter_type: str
    name: str
    model: str
    config: dict[str, Any]
    suggested_type: str


class CommissionRequest(BaseModel):
    pairing_code: str = Field(min_length=1)
