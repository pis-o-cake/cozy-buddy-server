"""Device control tools (Tool Calling)."""

from typing import Any

from app.domain.llm.tools.registry import ToolRegistry


@ToolRegistry.register(
    "control_device",
    description="스마트홈 장치를 제어합니다 (켜기/끄기/밝기 조절 등)",
    parameters={
        "type": "object",
        "properties": {
            "device_name": {"type": "string", "description": "장치 이름"},
            "action": {"type": "string", "description": "액션 (on/off/set_brightness)"},
            "value": {"description": "제어 값 (밝기 등)"},
        },
        "required": ["device_name", "action"],
    },
)
async def control_device(
    device_name: str, action: str, value: Any = None
) -> dict[str, Any]:
    """Device control tool."""
    from app.core.database import async_session
    from app.domain.device.service import DeviceService

    async with async_session() as db:
        service = DeviceService(db)
        return await service.control_device(
            device_name=device_name, action=action, value=value
        )


@ToolRegistry.register(
    "get_device_status",
    description="장치의 현재 상태를 조회합니다",
    parameters={
        "type": "object",
        "properties": {
            "device_name": {"type": "string", "description": "장치 이름"},
        },
        "required": ["device_name"],
    },
)
async def get_device_status(device_name: str) -> dict[str, Any]:
    """Device status query tool."""
    from app.core.database import async_session
    from app.domain.device.service import DeviceService

    async with async_session() as db:
        service = DeviceService(db)
        return await service.control_device(
            device_name=device_name, action="status"
        )
