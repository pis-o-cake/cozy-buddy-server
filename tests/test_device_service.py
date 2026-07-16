"""device 서비스 — room-aware 해석(§8-3)·재시도 실패 정책(§12-1)·프롬프트 블록(§7-1)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.exceptions import NotFoundError
from app.domain.device import service as device_service
from app.domain.device.models import Device, Room
from app.domain.device.service import AmbiguousDeviceError
from tests.fakes import FakeDeviceAdapter


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    monkeypatch.setattr(device_service, "RETRY_BACKOFF_SECONDS", (0.0, 0.0))
    FakeDeviceAdapter.reset()
    device_service.reset_adapter_cache()
    yield
    FakeDeviceAdapter.reset()
    device_service.reset_adapter_cache()


async def _seed(db) -> None:
    living = Room(name="거실", slug="living")
    bedroom = Room(name="침실", slug="bedroom")
    db.add_all([living, bedroom])
    await db.flush()
    db.add_all(
        [
            Device(
                name="거실 스탠드", room_id=living.id, device_type="lamp",
                adapter_type="fakeadp", capabilities=["on_off", "brightness"],
            ),
            Device(
                name="침실 스탠드", room_id=bedroom.id, device_type="lamp",
                adapter_type="fakeadp", capabilities=["on_off", "brightness"],
            ),
            Device(
                name="가습기", room_id=bedroom.id, device_type="plug",
                adapter_type="fakeadp", capabilities=["on_off"],
            ),
        ]
    )
    await db.commit()


@pytest.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        await _seed(session)
        yield session


async def test_explicit_room_overrides_hub_room(db):
    device, room, cross = await device_service.resolve_device(
        db, "스탠드", room="bedroom", hub_room="living"
    )
    assert device.name == "침실 스탠드"
    assert not cross


async def test_hub_room_priority(db):
    device, room, cross = await device_service.resolve_device(
        db, "스탠드", room=None, hub_room="living"
    )
    assert device.name == "거실 스탠드"
    assert not cross


async def test_unique_global_match_is_cross_room(db):
    # 발화 방(living)에 없지만 전체에서 유일 → 사용 + 위치 명시 플래그 (§8-3 3단계)
    device, room, cross = await device_service.resolve_device(
        db, "가습기", room=None, hub_room="living"
    )
    assert device.name == "가습기"
    assert room.slug == "bedroom"
    assert cross


async def test_ambiguous_raises_with_candidates(db):
    with pytest.raises(AmbiguousDeviceError) as exc_info:
        await device_service.resolve_device(db, "스탠드", room=None, hub_room=None)
    assert len(exc_info.value.candidates) == 2


async def test_alias_matches_type(db):
    # "불" → light|lamp 별칭 (§8-3 5단계) — 침실에는 lamp 하나뿐
    device, _, _ = await device_service.resolve_device(db, "불", room=None, hub_room="bedroom")
    assert device.name == "침실 스탠드"


async def test_no_match_raises_not_found(db):
    with pytest.raises(NotFoundError):
        await device_service.resolve_device(db, "에어컨", room=None, hub_room=None)


async def test_control_succeeds_after_transient_failure(db):
    FakeDeviceAdapter.fail_times = 1  # 1회 실패 → 재시도로 성공 (§12-1)
    result = await device_service.control_device(
        db, ref="가습기", room=None, hub_room=None, capability="on_off", value="on"
    )
    assert result["ok"] is True
    assert len(FakeDeviceAdapter.executed) == 2  # 원시도 + 재시도 1회


async def test_control_marks_offline_after_all_retries(db):
    FakeDeviceAdapter.fail_times = 99
    result = await device_service.control_device(
        db, ref="가습기", room=None, hub_room=None, capability="on_off", value="on"
    )
    assert result["ok"] is False
    assert len(FakeDeviceAdapter.executed) == 3  # 원시도 + 재시도 2회 (§12-1)
    device = next(d for d, _ in await device_service._load_devices(db) if d.name == "가습기")
    assert device.online is False


async def test_unsupported_capability_rejected(db):
    result = await device_service.control_device(
        db, ref="가습기", room=None, hub_room=None, capability="brightness", value=50
    )
    assert result["ok"] is False
    assert "supported" in result
    assert FakeDeviceAdapter.executed == []  # 어댑터 호출 전에 차단


async def test_prompt_block_groups_by_room(db):
    block = await device_service.prompt_block(db)
    assert block is not None
    assert "거실(living)" in block
    assert "침실(bedroom)" in block
    assert "거실 스탠드(lamp: brightness, on_off)" in block
