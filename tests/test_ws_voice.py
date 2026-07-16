"""음성 WS 게이트웨이 통합 테스트 (설계서 §5-1) — fake STT/TTS/LLM 사용.

aiosqlite 커넥션이 이벤트 루프에 묶이므로, 앱(포털 루프)이 직접 열도록
파일 기반 SQLite + 환경변수 주입 방식으로 구성한다.
"""

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from alembic.config import Config
from starlette.testclient import TestClient

from alembic import command
from app.config import get_settings
from app.core.database import reset_database_state
from app.core.security import create_jwt, hash_token
from app.domain.voice import runtime
from tests.fakes import FakeSTT

_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def ws_token(tmp_path, monkeypatch):
    db_path = tmp_path / "ws.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("ALEMBIC_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("STT_PROVIDER", "fake")
    monkeypatch.setenv("TTS_PROVIDER", "fake")
    monkeypatch.setenv("LLM_PROVIDER", "fake")
    get_settings.cache_clear()
    reset_database_state()
    runtime.reset_runtime()

    config = Config(str(_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(_ROOT / "alembic"))
    command.upgrade(config, "head")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO hubs (hub_id, room_id, name, token_hash) VALUES (?, NULL, ?, ?)",
            ("test-hub", "테스트 허브", hash_token("device-token")),
        )
        conn.commit()

    yield create_jwt("test-hub")

    get_settings.cache_clear()
    reset_database_state()
    runtime.reset_runtime()


def _connect(client: TestClient, token: str):
    ws = client.websocket_connect("/ws/hub")
    websocket = ws.__enter__()
    websocket.send_json({"type": "auth", "token": token})
    assert websocket.receive_json()["type"] == "auth.ok"
    return ws, websocket


def _collect_until_idle(websocket) -> list[dict[str, Any]]:
    """state=idle(파이프라인 종료 신호)까지 수신 — 바이너리는 {type:_binary}로 치환."""
    collected: list[dict[str, Any]] = []
    for _ in range(300):  # 무한 대기 방어
        message = websocket.receive()
        if message.get("text") is not None:
            data = json.loads(message["text"])
            collected.append(data)
            if data["type"] == "state" and data.get("value") == "idle":
                return collected
        elif message.get("bytes") is not None:
            collected.append({"type": "_binary", "payload": message["bytes"]})
    raise AssertionError("state=idle not received")


def _types(collected: list[dict[str, Any]]) -> list[str]:
    return [m["type"] for m in collected]


def test_auth_with_bad_token_is_rejected(ws_token):
    from app.main import app

    client = TestClient(app)
    with client.websocket_connect("/ws/hub") as websocket:
        websocket.send_json({"type": "auth", "token": "bogus"})
        assert websocket.receive_json() == {"type": "auth.error", "code": "invalid_token"}


def test_ping_pong(ws_token):
    from app.main import app

    ws, websocket = _connect(TestClient(app), ws_token)
    try:
        websocket.send_json({"type": "ping", "ts": 123})
        assert websocket.receive_json() == {"type": "pong", "ts": 123}
    finally:
        ws.__exit__(None, None, None)


def test_text_query_full_flow(ws_token):
    from app.main import app

    ws, websocket = _connect(TestClient(app), ws_token)
    try:
        websocket.send_json({"type": "text.query", "session_id": "s1", "text": "불 꺼줘"})
        collected = _collect_until_idle(websocket)  # 마지막 state=idle까지
        # 파이프라인 순서 (§4): thinking → llm.delta → tts.start → 오디오 → tts.end → response
        types = _types(collected)
        assert types[0] == "state" and collected[0]["value"] == "thinking"
        assert "llm.delta" in types
        assert types.index("tts.start") < types.index("_binary") < types.index("tts.end")
        response = next(m for m in collected if m["type"] == "response")
        assert response["text"] == "거실 조명을 껐어요."
        assert collected[-1] == {"type": "state", "value": "idle"}
        # 다운링크 오디오는 0x02 태그 (§5-1)
        binary = next(m for m in collected if m["type"] == "_binary")
        assert binary["payload"][0] == 0x02
    finally:
        ws.__exit__(None, None, None)


def test_binary_utterance_flow(ws_token):
    from app.main import app

    ws, websocket = _connect(TestClient(app), ws_token)
    try:
        websocket.send_json(
            {
                "type": "utterance.start",
                "session_id": "u1",
                "hub_id": "test-hub",
                "room": None,
                "audio": {"codec": "pcm16", "rate": 16000, "ch": 1},
            }
        )
        websocket.send_bytes(b"\x01" + b"\x00\x00" * 320)  # 20ms 프레임
        websocket.send_json({"type": "utterance.end", "session_id": "u1"})
        collected = _collect_until_idle(websocket)
        stt_final = next(m for m in collected if m["type"] == "stt.final")
        assert stt_final["text"] == "불 꺼줘"
        assert any(m["type"] == "response" for m in collected)
    finally:
        ws.__exit__(None, None, None)


def test_low_confidence_asks_to_repeat(ws_token):
    from app.core.i18n import t
    from app.domain.voice.providers.stt_base import STTResult
    from app.main import app

    FakeSTT.next_result = STTResult(text="웅얼웅얼", confidence=0.1, duration_ms=10)
    try:
        ws, websocket = _connect(TestClient(app), ws_token)
        try:
            websocket.send_json({"type": "utterance.start", "session_id": "u2"})
            websocket.send_bytes(b"\x01" + b"\x00\x00" * 320)
            websocket.send_json({"type": "utterance.end", "session_id": "u2"})
            collected = _collect_until_idle(websocket)
            types = _types(collected)
            # 저신뢰는 error가 아닌 정상 되묻기 response 경로 (§12-1)
            assert "stt.final" not in types
            assert "error" not in types
            response = next(m for m in collected if m["type"] == "response")
            assert response["text"] == t("voice.repeat_please")
        finally:
            ws.__exit__(None, None, None)
    finally:
        FakeSTT.next_result = STTResult(text="불 꺼줘", confidence=0.95, duration_ms=12)
