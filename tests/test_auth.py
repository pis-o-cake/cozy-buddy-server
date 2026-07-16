"""페어링 → device token → JWT 흐름 (설계서 §11)."""


async def _pair(client, hub_id: str = "living-01") -> str:
    """페어링을 완료하고 device token을 반환한다."""
    code = (await client.post("/api/auth/pairing")).json()["code"]
    response = await client.post(
        "/api/auth/pair", json={"code": code, "hub_id": hub_id, "name": "거실 허브"}
    )
    assert response.status_code == 200
    return response.json()["device_token"]


async def test_full_pairing_flow(client):
    device_token = await _pair(client)

    token_response = await client.post("/api/auth/token", json={"device_token": device_token})
    assert token_response.status_code == 200
    body = token_response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["expires_in"] > 0


async def test_pair_with_invalid_code(client):
    response = await client.post(
        "/api/auth/pair", json={"code": "000000", "hub_id": "x-01", "name": "허브"}
    )
    assert response.status_code == 400
    assert response.json()["code"] == "pairing_code_invalid"


async def test_pairing_code_is_single_use(client):
    code = (await client.post("/api/auth/pairing")).json()["code"]
    first = await client.post(
        "/api/auth/pair", json={"code": code, "hub_id": "a-01", "name": "허브"}
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/pair", json={"code": code, "hub_id": "b-01", "name": "허브"}
    )
    assert second.status_code == 400


async def test_duplicate_hub_id_conflicts(client):
    await _pair(client, hub_id="dup-01")
    code = (await client.post("/api/auth/pairing")).json()["code"]
    response = await client.post(
        "/api/auth/pair", json={"code": code, "hub_id": "dup-01", "name": "허브"}
    )
    assert response.status_code == 409


async def test_unknown_device_token_is_unauthorized(client):
    response = await client.post("/api/auth/token", json={"device_token": "bogus"})
    assert response.status_code == 401


async def test_unpair_revokes_token(client):
    device_token = await _pair(client, hub_id="gone-01")

    delete_response = await client.delete("/api/auth/hubs/gone-01")
    assert delete_response.status_code == 204

    token_response = await client.post("/api/auth/token", json={"device_token": device_token})
    assert token_response.status_code == 401
