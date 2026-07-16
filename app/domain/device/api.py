"""device 도메인 API (설계서 §5-2 — /api/devices)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.domain.device import crud, service, taxonomy
from app.domain.device.adapters.base import AdapterNotSupportedError
from app.domain.device.adapters.matter import MatterAdapter
from app.domain.device.schemas import (
    CommandRequest,
    CommissionRequest,
    DeviceCreate,
    DeviceOut,
    DevicePatch,
    DiscoveredOut,
)

PREFIX = "/api/devices"
router = APIRouter(tags=["device"])


@router.get("", response_model=list[DeviceOut])
async def list_devices(session: AsyncSession = Depends(get_session)) -> list[DeviceOut]:
    return [DeviceOut.model_validate(d) for d in await crud.list_devices(session)]


@router.post("", response_model=DeviceOut)
async def create_device(
    body: DeviceCreate, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    """기기 등록 (§8-2 마지막 단계). capabilities 생략 시 taxonomy 기본 프로파일."""
    if await crud.get_room(session, body.room_id) is None:
        raise NotFoundError(f"room {body.room_id} not found")
    capabilities = body.capabilities
    if capabilities is None:
        capabilities = sorted(taxonomy.default_capabilities(body.device_type))
    device = await crud.create_device(
        session,
        name=body.name,
        room_id=body.room_id,
        device_type=body.device_type,
        adapter_type=body.adapter_type,
        capabilities=capabilities,
        config=body.config,
    )
    return DeviceOut.model_validate(device)


@router.get("/{device_id}", response_model=DeviceOut)
async def get_device(device_id: int, session: AsyncSession = Depends(get_session)) -> DeviceOut:
    device = await crud.get_device(session, device_id)
    if device is None:
        raise NotFoundError(f"device {device_id} not found")
    return DeviceOut.model_validate(device)


@router.patch("/{device_id}", response_model=DeviceOut)
async def patch_device(
    device_id: int, body: DevicePatch, session: AsyncSession = Depends(get_session)
) -> DeviceOut:
    device = await crud.get_device(session, device_id)
    if device is None:
        raise NotFoundError(f"device {device_id} not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(device, field, value)
    await session.commit()
    await session.refresh(device)
    return DeviceOut.model_validate(device)


@router.delete("/{device_id}", status_code=204)
async def delete_device(device_id: int, session: AsyncSession = Depends(get_session)) -> None:
    device = await crud.get_device(session, device_id)
    if device is None:
        raise NotFoundError(f"device {device_id} not found")
    await crud.delete_device(session, device)


@router.post("/discover", response_model=list[DiscoveredOut])
async def discover(adapter: str | None = None) -> list[DiscoveredOut]:
    """어댑터별 LAN 스캔 (§8-2 자동 검색)."""
    found = await service.discover(adapter)
    return [DiscoveredOut(**vars(d)) for d in found]


@router.post("/commission", status_code=501)
async def commission(body: CommissionRequest) -> dict[str, str]:
    """Matter QR/셋업코드 커미셔닝 (§8-2) — matterjs-server 확보 전까지 미지원 슬롯."""
    try:
        await MatterAdapter().commission(body.pairing_code)
    except AdapterNotSupportedError as exc:
        return {"status": "not_implemented", "detail": str(exc)}
    return {"status": "ok"}


@router.post("/{device_id}/identify", status_code=204)
async def identify(device_id: int, session: AsyncSession = Depends(get_session)) -> None:
    """기기 깜빡임/토글 물리 식별 (§8-2 연결 확인)."""
    await service.identify(session, device_id)


@router.post("/{device_id}/command")
async def command(
    device_id: int, body: CommandRequest, session: AsyncSession = Depends(get_session)
) -> dict:
    """터치 제어 (§5-2) — 음성과 동일한 실패 정책 경로를 탄다."""
    device = await crud.get_device(session, device_id)
    if device is None:
        raise NotFoundError(f"device {device_id} not found")
    return await service.control_device(
        session,
        ref=device.name,
        room=None,
        hub_room=None,
        capability=body.capability,
        value=body.value,
    )


@router.get("/{device_id}/state")
async def get_state(device_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    device = await crud.get_device(session, device_id)
    if device is None:
        raise NotFoundError(f"device {device_id} not found")
    return await service.query_device(session, ref=device.name, room=None, hub_room=None)
