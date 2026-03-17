"""Device domain schemas."""

from typing import Any

from pydantic import BaseModel, Field


class DeviceCreate(BaseModel):
    """Device registration request."""

    name: str = Field(..., description="Device name")
    device_type: str = Field(..., description="Device type (light/plug/sensor)")
    adapter_type: str = Field(..., description="Adapter type (tapo/ir)")
    location: str = Field(..., description="Location (living room/bedroom etc.)")
    config: dict[str, Any] = Field(default_factory=dict, description="Device config (IP etc.)")


class DeviceResponse(BaseModel):
    """Device response."""

    id: int
    name: str
    device_type: str
    adapter_type: str
    location: str
    config: dict[str, Any]
    is_active: bool

    model_config = {"from_attributes": True}


class DeviceControlRequest(BaseModel):
    """Device control request."""

    action: str = Field(..., description="Control action (on/off/set_brightness etc.)")
    value: Any = Field(default=None, description="Control value")
