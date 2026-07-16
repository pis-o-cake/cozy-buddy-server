"""device 도메인 서비스 — room-aware 해석(§8-3)·실패 정책(§12-1)·프롬프트 블록(§7-1)."""

import asyncio
from typing import Any

import sqlalchemy as sa
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.websocket import hub_manager
from app.domain.device import taxonomy
from app.domain.device.adapters.base import (
    CommandResult,
    DeviceAdapter,
    DeviceCommand,
    DiscoveredDevice,
    adapter_registry,
)

# 어댑터 등록 트리거 — 새 어댑터 추가 시 여기에 import 한 줄
from app.domain.device.adapters.kasa import KasaAdapter  # noqa: F401
from app.domain.device.adapters.matter import MatterAdapter  # noqa: F401
from app.domain.device.models import Device, Room

RETRY_BACKOFF_SECONDS: tuple[float, ...] = (0.5, 1.0)  # 2회 재시도 (§12-1)

_adapter_cache: dict[str, DeviceAdapter] = {}


class AmbiguousDeviceError(Exception):
    """동일 지칭 기기 다수 — 확인 질문 유도 (§8-3 4단계)."""

    def __init__(self, candidates: list[str]) -> None:
        self.candidates = candidates
        super().__init__(f"ambiguous device: {', '.join(candidates)}")


def get_adapter(adapter_type: str) -> DeviceAdapter:
    if adapter_type not in _adapter_cache:
        settings = get_settings()
        if adapter_type == "kasa":
            _adapter_cache[adapter_type] = adapter_registry.build(
                "kasa", username=settings.kasa_username, password=settings.kasa_password
            )
        else:
            _adapter_cache[adapter_type] = adapter_registry.build(adapter_type)
    return _adapter_cache[adapter_type]


def reset_adapter_cache() -> None:
    """테스트 전용."""
    _adapter_cache.clear()


# ── room-aware 해석 (§8-3) ─────────────────────────────────────


def _normalize(text: str) -> str:
    return text.replace(" ", "").strip().lower()


async def _load_devices(session: AsyncSession) -> list[tuple[Device, Room]]:
    rows = await session.execute(sa.select(Device, Room).join(Room, Device.room_id == Room.id))
    return [(device, room) for device, room in rows.all()]


def _match(ref: str, device: Device) -> bool:
    ref_norm = _normalize(ref)
    name_norm = _normalize(device.name)
    if ref_norm == name_norm or ref_norm in name_norm or name_norm in ref_norm:
        return True
    # 타입 별칭 매칭: "불" → light|lamp (§8-3 5단계)
    for alias, types in taxonomy.TYPE_ALIASES.items():
        if alias in ref and device.device_type in types:
            return True
    return False


async def resolve_device(
    session: AsyncSession, ref: str, *, room: str | None, hub_room: str | None
) -> tuple[Device, Room, bool]:
    """자연어 지칭을 기기로 해석한다.

    Returns:
        (Device, Room, cross_room) — cross_room은 허브 방 밖에서 찾았음(응답에 위치 명시 — §8-3).

    Raises:
        NotFoundError: 매칭 없음.
        AmbiguousDeviceError: 후보 다수.
    """
    all_devices = await _load_devices(session)
    matched = [(d, r) for d, r in all_devices if _match(ref, d)]
    if not matched:
        raise NotFoundError(f"no device matched '{ref}'")

    # 1) room 명시 → 그 방으로 한정
    if room:
        room_norm = _normalize(room)
        scoped = [
            (d, r)
            for d, r in matched
            if room_norm in (_normalize(r.slug), _normalize(r.name))
        ]
        if len(scoped) == 1:
            return scoped[0][0], scoped[0][1], False
        if len(scoped) > 1:
            raise AmbiguousDeviceError([f"{r.name} {d.name}" for d, r in scoped])
        raise NotFoundError(f"no device matched '{ref}' in room '{room}'")

    # 2) 발화 허브의 방 우선
    if hub_room:
        hub_norm = _normalize(hub_room)
        scoped = [(d, r) for d, r in matched if _normalize(r.slug) == hub_norm]
        if len(scoped) == 1:
            return scoped[0][0], scoped[0][1], False
        if len(scoped) > 1:
            raise AmbiguousDeviceError([f"{r.name} {d.name}" for d, r in scoped])

    # 3) 전체 탐색 — 유일하면 사용 (위치 명시 응답)
    if len(matched) == 1:
        return matched[0][0], matched[0][1], True
    raise AmbiguousDeviceError([f"{r.name} {d.name}" for d, r in matched])


# ── 제어/조회 + 실패 정책 (§12-1) ─────────────────────────────


async def execute_with_retry(device: Device, command: DeviceCommand) -> CommandResult:
    """어댑터 실행 + 2회 재시도(지수 백오프). 최종 실패만 실패로 보고."""
    adapter = get_adapter(device.adapter_type)
    result = CommandResult(ok=False, detail="not attempted")
    for attempt, backoff in enumerate((0.0, *RETRY_BACKOFF_SECONDS)):
        if backoff:
            await asyncio.sleep(backoff)
        try:
            result = await adapter.execute(device, command)
        except Exception as exc:
            result = CommandResult(ok=False, detail=str(exc))
        if result.ok:
            return result
        logger.warning(
            "device command failed (attempt {}): {} {} — {}",
            attempt + 1,
            device.name,
            command.capability,
            result.detail,
        )
    return result


async def control_device(
    session: AsyncSession,
    *,
    ref: str,
    room: str | None,
    hub_room: str | None,
    capability: str,
    value: Any,
) -> dict[str, Any]:
    """음성/터치 공용 제어 진입점. 결과는 tool 결과로도 쓰이는 dict."""
    device, device_room, cross_room = await resolve_device(
        session, ref, room=room, hub_room=hub_room
    )

    allowed = set(device.capabilities or taxonomy.default_capabilities(device.device_type))
    if capability not in allowed:
        return {
            "ok": False,
            "error": f"device '{device.name}' does not support '{capability}'",
            "supported": sorted(allowed),
        }

    result = await execute_with_retry(device, DeviceCommand(capability=capability, value=value))
    device.online = result.ok
    await session.commit()

    if result.ok:
        await hub_manager.broadcast_all(
            {
                "type": "device.state_changed",
                "device_id": device.id,
                "state": {capability: value, "online": True},
            }
        )
        return {
            "ok": True,
            "device": device.name,
            "room": device_room.slug,
            "cross_room": cross_room,  # 발화 방 밖 기기 — 응답에 위치 명시 (§8-3)
            "capability": capability,
            "value": value,
        }
    return {"ok": False, "device": device.name, "error": result.detail or "device offline"}


async def query_device(
    session: AsyncSession, *, ref: str, room: str | None, hub_room: str | None
) -> dict[str, Any]:
    device, device_room, _ = await resolve_device(session, ref, room=room, hub_room=hub_room)
    adapter = get_adapter(device.adapter_type)
    try:
        state = await adapter.get_state(device)
    except Exception as exc:
        device.online = False
        await session.commit()
        return {"ok": False, "device": device.name, "error": str(exc)}
    device.online = state.online
    await session.commit()
    return {
        "ok": True,
        "device": device.name,
        "room": device_room.slug,
        "online": state.online,
        "state": state.attributes,
    }


# ── 검색/식별 (§8-2) ──────────────────────────────────────────


async def discover(adapter_type: str | None = None) -> list[DiscoveredDevice]:
    settings = get_settings()
    targets = [adapter_type] if adapter_type else [
        name.strip() for name in settings.iot_adapters.split(",") if name.strip()
    ]
    found: list[DiscoveredDevice] = []
    for name in targets:
        try:
            found.extend(await get_adapter(name).discover())
        except Exception as exc:
            # 어댑터별 장애 격리 (§12-1) — 하나가 죽어도 나머지는 진행
            logger.warning("discover failed for adapter {}: {}", name, exc)
    return found


async def identify(session: AsyncSession, device_id: int) -> None:
    device = await session.get(Device, device_id)
    if device is None:
        raise NotFoundError(f"device {device_id} not found")
    await get_adapter(device.adapter_type).identify(device)


# ── system prompt 기기 블록 (§7-1 블록4) ──────────────────────


async def prompt_block(session: AsyncSession) -> str | None:
    """방별 기기 목록 문자열. 기기가 없으면 None (호출측이 기본 문구 사용)."""
    devices = await _load_devices(session)
    if not devices:
        return None
    by_room: dict[str, list[str]] = {}
    for device, room in devices:
        caps = ", ".join(sorted(device.capabilities or []))
        entry = f"{device.name}({device.device_type}: {caps})"
        by_room.setdefault(f"{room.name}({room.slug})", []).append(entry)
    lines = ["등록 기기:"]
    for room_label, entries in sorted(by_room.items()):
        lines.append(f"- {room_label}: {' / '.join(entries)}")
    return "\n".join(lines)
