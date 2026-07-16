async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_system_status_exposes_provider_flags_only(client):
    response = await client.get("/api/system/status")
    assert response.status_code == 200
    body = response.json()
    assert set(body["llm_providers"]) == {"anthropic", "gemini", "llamacpp", "openai"}
    # 키 값이 아닌 구성 여부(bool)만 노출되어야 한다 (설계서 §11)
    assert all(isinstance(v, bool) for v in body["llm_providers"].values())
