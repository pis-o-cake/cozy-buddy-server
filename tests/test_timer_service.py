"""timer 서비스 — 발화 시각 계산·잡 등록·timer.fired push (설계서 §5-1 · §9)."""

from datetime import timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database import override_session_factory
from app.core.scheduler import scheduler, shutdown_scheduler, start_scheduler
from app.core.websocket import hub_manager
from app.domain.auth.models import Hub
from app.domain.timer import service
from app.domain.timer.service import _now


def test_parse_fires_at_duration():
    fires_at = service.parse_fires_at(duration_sec=180, at=None)
    assert timedelta(seconds=179) < (fires_at - _now()) <= timedelta(seconds=181)


def test_parse_fires_at_hhmm_rolls_to_next_day():
    past = (_now() - timedelta(hours=1)).strftime("%H:%M")
    fires_at = service.parse_fires_at(duration_sec=None, at=past)
    assert fires_at > _now()  # 이미 지난 시각은 내일로


def test_parse_fires_at_requires_input():
    with pytest.raises(ValueError):
        service.parse_fires_at(duration_sec=None, at=None)


@pytest.fixture
async def timer_env(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    override_session_factory(factory)
    start_scheduler()
    async with factory() as session:
        hub = Hub(hub_id="living-01", name="거실 허브", token_hash="t" * 64)
        session.add(hub)
        await session.commit()
        await session.refresh(hub)
        yield session, hub
    shutdown_scheduler()
    override_session_factory(None)


async def test_create_timer_registers_job(timer_env):
    session, hub = timer_env
    timer = await service.create_timer(
        session, hub_pk=hub.id, kind="timer", fires_at=_now() + timedelta(hours=1), label="라면"
    )
    assert scheduler.get_job(f"timer-{timer.id}") is not None

    await service.cancel_timer(session, hub_pk=hub.id, label="라면")
    assert scheduler.get_job(f"timer-{timer.id}") is None


async def test_fire_pushes_and_deletes_one_shot(timer_env, monkeypatch):
    session, hub = timer_env
    pushed: list[tuple[str, dict]] = []

    async def record(hub_id: str, payload: dict) -> bool:
        pushed.append((hub_id, payload))
        return True

    monkeypatch.setattr(hub_manager, "send_to", record)

    timer = await service.create_timer(
        session, hub_pk=hub.id, kind="alarm", fires_at=_now() + timedelta(hours=1), label="기상"
    )
    await service._fire(timer.id)

    assert pushed[0][0] == "living-01"
    assert pushed[0][1]["type"] == "timer.fired"
    assert pushed[0][1]["kind"] == "alarm"
    # 일회성은 발화 후 정리 (§9) — _fire가 별도 세션에서 삭제했으므로 새 세션으로 확인
    from app.core.database import get_session_factory
    from app.domain.timer import crud

    async with get_session_factory()() as fresh:
        assert await crud.get_timer(fresh, timer.id) is None
