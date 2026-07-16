"""python-kasa 어댑터 — TP-Link Kasa/Tapo LAN 로컬 제어 (설계서 §8-1 1차 어댑터).

- Tapo 기기는 로컬 핸드셰이크에 Tapo 계정 자격증명이 필요하다 → `.env`
  KASA_USERNAME/KASA_PASSWORD (Device.config의 credentials 우선).
- 의존성은 `pip install -e ".[iot]"` — 지연 import.
"""

import asyncio
from typing import Any, ClassVar

from loguru import logger

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

_DISCOVER_TIMEOUT_SECONDS = 5


def _suggest_type(kasa_device: Any) -> str:
    """kasa 기기 종류 → taxonomy 추정 (등록 시 사용자가 확정 — §8-2)."""
    device_type = str(getattr(kasa_device, "device_type", "")).lower()
    if "bulb" in device_type:
        return "light"
    if "strip" in device_type or "lightstrip" in device_type:
        return "strip"
    if "plug" in device_type:
        return "plug"
    if "switch" in device_type or "dimmer" in device_type:
        return "switch"
    return "plug"


@adapter_registry.register("kasa")
class KasaAdapter(DeviceAdapter):
    adapter_type: ClassVar[str] = "kasa"

    def __init__(self, *, username: str = "", password: str = "") -> None:
        self._username = username
        self._password = password

    # ── 연결 ──────────────────────────────────────────────────

    async def _connect(self, device: Device) -> Any:
        from kasa import Device as KasaDevice
        from kasa import DeviceConfig
        from kasa.credentials import Credentials

        host = device.config.get("host")
        if not host:
            raise AdapterNotSupportedError(f"device '{device.name}' has no host in config")
        username = device.config.get("username", self._username)
        password = device.config.get("password", self._password)
        credentials = Credentials(username, password) if username else None
        config = DeviceConfig(host=host, credentials=credentials)
        connected = await KasaDevice.connect(config=config)
        await connected.update()
        return connected

    # ── 계약 구현 ─────────────────────────────────────────────

    async def discover(self) -> list[DiscoveredDevice]:
        from kasa import Discover

        kwargs: dict[str, Any] = {"discovery_timeout": _DISCOVER_TIMEOUT_SECONDS}
        if self._username:
            kwargs["username"] = self._username
            kwargs["password"] = self._password
        found = await Discover.discover(**kwargs)

        results: list[DiscoveredDevice] = []
        for host, kasa_device in found.items():
            results.append(
                DiscoveredDevice(
                    adapter_type=self.adapter_type,
                    name=getattr(kasa_device, "alias", None) or host,
                    model=getattr(kasa_device, "model", "unknown"),
                    config={"host": host},
                    suggested_type=_suggest_type(kasa_device),
                )
            )
        logger.info("kasa discover found {} devices", len(results))
        return results

    async def identify(self, device: Device) -> None:
        """on/off 2회 토글로 물리 식별 (§8-2 — 오등록 방지)."""
        connected = await self._connect(device)
        try:
            original_on = bool(connected.is_on)
            for _ in range(2):
                await (connected.turn_off() if original_on else connected.turn_on())
                await connected.update()
                await asyncio.sleep(0.6)
                await (connected.turn_on() if original_on else connected.turn_off())
                await connected.update()
                await asyncio.sleep(0.6)
        finally:
            await connected.disconnect()

    async def get_state(self, device: Device) -> DeviceState:
        connected = await self._connect(device)
        try:
            attributes: dict[str, Any] = {"on_off": "on" if connected.is_on else "off"}
            light = self._light_module(connected)
            if light is not None:
                if getattr(light, "brightness", None) is not None:
                    attributes["brightness"] = light.brightness
                if getattr(light, "color_temp", None):
                    attributes["color_temp"] = light.color_temp
            return DeviceState(online=True, attributes=attributes)
        finally:
            await connected.disconnect()

    async def execute(self, device: Device, command: DeviceCommand) -> CommandResult:
        connected = await self._connect(device)
        try:
            match command.capability:
                case "on_off":
                    turn_on = str(command.value).lower() in ("on", "true", "1")
                    await (connected.turn_on() if turn_on else connected.turn_off())
                case "brightness":
                    light = self._light_module(connected)
                    if light is None:
                        return CommandResult(ok=False, detail="device has no light module")
                    await light.set_brightness(int(command.value))
                case "color_temp":
                    light = self._light_module(connected)
                    if light is None:
                        return CommandResult(ok=False, detail="device has no light module")
                    await light.set_color_temp(int(command.value))
                case unsupported:
                    return CommandResult(ok=False, detail=f"unsupported capability: {unsupported}")
            return CommandResult(ok=True)
        finally:
            await connected.disconnect()

    @staticmethod
    def _light_module(connected: Any) -> Any:
        from kasa import Module

        return connected.modules.get(Module.Light)
