"""device/room REST 스모크 (설계서 §5-2) — fake adapter 사용."""

import pytest

from app.domain.device import service as device_service
from tests.fakes import FakeDeviceAdapter


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(device_service, "RETRY_BACKOFF_SECONDS", (0.0, 0.0))
    FakeDeviceAdapter.reset()
    device_service.reset_adapter_cache()
    yield
    FakeDeviceAdapter.reset()
    device_service.reset_adapter_cache()


async def _create_room_and_device(client) -> tuple[int, int]:
    room = (await client.post("/api/rooms", json={"name": "거실", "slug": "living"})).json()
    device_response = await client.post(
        "/api/devices",
        json={
            "name": "거실 플러그",
            "room_id": room["id"],
            "device_type": "plug",
            "adapter_type": "fakeadp",
            "config": {"host": "10.0.0.5"},
        },
    )
    assert device_response.status_code == 200
    return room["id"], device_response.json()["id"]


async def test_device_crud_and_default_capabilities(client):
    _, device_id = await _create_room_and_device(client)
    device = (await client.get(f"/api/devices/{device_id}")).json()
    # capabilities 생략 → taxonomy 기본 프로파일 (§8-1)
    assert set(device["capabilities"]) == {"on_off", "energy"}

    listed = (await client.get("/api/devices")).json()
    assert len(listed) == 1

    assert (await client.delete(f"/api/devices/{device_id}")).status_code == 204
    assert (await client.get(f"/api/devices/{device_id}")).status_code == 404


async def test_unknown_device_type_rejected(client):
    room = (await client.post("/api/rooms", json={"name": "거실", "slug": "living"})).json()
    response = await client.post(
        "/api/devices",
        json={
            "name": "이상한 것",
            "room_id": room["id"],
            "device_type": "warp-drive",
            "adapter_type": "fakeadp",
        },
    )
    assert response.status_code == 422


async def test_command_endpoint_controls_device(client):
    _, device_id = await _create_room_and_device(client)
    response = await client.post(
        f"/api/devices/{device_id}/command", json={"capability": "on_off", "value": "on"}
    )
    body = response.json()
    assert body["ok"] is True
    assert FakeDeviceAdapter.executed == [("거실 플러그", "on_off", "on")]


async def test_duplicate_room_slug_conflicts(client):
    await client.post("/api/rooms", json={"name": "거실", "slug": "living"})
    response = await client.post("/api/rooms", json={"name": "거실2", "slug": "living"})
    assert response.status_code == 409


async def test_commission_is_explicit_not_implemented(client):
    response = await client.post("/api/devices/commission", json={"pairing_code": "1234-567"})
    assert response.status_code == 501  # matterjs-server 확보 전 명시적 미지원 (§8-1 슬롯)
