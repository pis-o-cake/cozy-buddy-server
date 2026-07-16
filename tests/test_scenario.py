"""scenario 실행 엔진 — 순서·병렬·부분 실패 (설계서 §9-2 · §12-1)."""

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.domain.device import service as device_service
from app.domain.device.models import Device, Room
from app.domain.scenario import crud, service
from app.domain.scenario.models import ScenarioAction
from tests.fakes import FakeDeviceAdapter


@pytest.fixture(autouse=True)
def _fast_retry(monkeypatch):
    monkeypatch.setattr(device_service, "RETRY_BACKOFF_SECONDS", (0.0, 0.0))
    FakeDeviceAdapter.reset()
    device_service.reset_adapter_cache()
    yield
    FakeDeviceAdapter.reset()
    device_service.reset_adapter_cache()


def test_group_actions_batches_consecutive_parallel_groups():
    def action(order: int, group: int | None) -> ScenarioAction:
        return ScenarioAction(
            scenario_id=1, order=order, parallel_group=group, command={"type": "wait", "sec": 0}
        )

    groups = service._group_actions(
        [action(1, None), action(2, 1), action(3, 1), action(4, None)]
    )
    assert [len(g) for g in groups] == [1, 2, 1]


@pytest.fixture
async def db(db_engine):
    factory = async_sessionmaker(db_engine, expire_on_commit=False)
    async with factory() as session:
        room = Room(name="거실", slug="living")
        session.add(room)
        await session.flush()
        devices = [
            Device(
                name=f"기기{i}", room_id=room.id, device_type="plug",
                adapter_type="fakeadp", capabilities=["on_off"],
            )
            for i in range(3)
        ]
        session.add_all(devices)
        await session.commit()
        for d in devices:
            await session.refresh(d)
        yield session, devices


async def test_execute_runs_actions_in_order_with_parallel_group(db):
    session, devices = db
    scenario = await crud.create_scenario(
        session,
        name="굿나잇",
        triggers=[{"type": "voice", "phrases": ["잘자"]}],
        enabled=True,
        actions=[
            {
                "order": 1,
                "device_id": devices[0].id,
                "command": {"type": "device_command", "capability": "on_off", "value": "off"},
            },
            {
                "order": 2,
                "parallel_group": 1,
                "device_id": devices[1].id,
                "command": {"type": "device_command", "capability": "on_off", "value": "off"},
            },
            {
                "order": 3,
                "parallel_group": 1,
                "device_id": devices[2].id,
                "command": {"type": "device_command", "capability": "on_off", "value": "off"},
            },
            {"order": 4, "command": {"type": "wait", "sec": 0}},
        ],
    )
    run = await service.execute_scenario(session, scenario)

    assert run.ok is True
    assert [r.order for r in run.results] == [1, 2, 3, 4]
    assert len(FakeDeviceAdapter.executed) == 3
    assert FakeDeviceAdapter.executed[0][0] == "기기0"  # order 1이 병렬 그룹보다 먼저


async def test_partial_failure_continues_and_reports(db):
    session, devices = db
    FakeDeviceAdapter.fail_times = 3  # 첫 액션의 전체 시도(3회)만 실패
    scenario = await crud.create_scenario(
        session,
        name="굿모닝",
        triggers=[],
        enabled=True,
        actions=[
            {
                "order": 1,
                "device_id": devices[0].id,
                "command": {"type": "device_command", "capability": "on_off", "value": "on"},
            },
            {
                "order": 2,
                "device_id": devices[1].id,
                "command": {"type": "device_command", "capability": "on_off", "value": "on"},
            },
        ],
    )
    run = await service.execute_scenario(session, scenario)

    assert run.ok is False  # 부분 실패 (§12-1)
    assert [r.ok for r in run.results] == [False, True]  # 실패해도 다음 액션 진행


async def test_unknown_action_type_is_reported(db):
    session, _ = db
    scenario = await crud.create_scenario(
        session,
        name="이상한것",
        triggers=[],
        enabled=True,
        actions=[{"order": 1, "command": {"type": "teleport"}}],
    )
    run = await service.execute_scenario(session, scenario)
    assert run.ok is False
    assert "unknown action type" in run.results[0].detail


async def test_enabled_names_for_prompt(db):
    session, _ = db
    await crud.create_scenario(session, name="굿모닝", triggers=[], enabled=True, actions=[])
    await crud.create_scenario(session, name="꺼진것", triggers=[], enabled=False, actions=[])
    names = await service.enabled_names(session)
    assert "굿모닝" in names
    assert "꺼진것" not in names
