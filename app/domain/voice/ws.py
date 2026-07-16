"""허브 음성 WS 게이트웨이 — `/ws/hub` (설계서 §5-1).

연결 직후 1회 `auth{token(JWT)}` 필수. 인증 후 텍스트 프레임=제어 JSON,
바이너리 프레임=오디오(첫 1바이트 스트림 태그)로 다중화한다.
"""

import asyncio
from datetime import UTC, datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from app.core.database import get_session_factory
from app.core.exceptions import UnauthorizedError
from app.core.security import decode_jwt
from app.core.websocket import hub_manager
from app.domain.auth import crud as auth_crud
from app.domain.device.models import Room
from app.domain.voice.service import VoiceSessionHandler

router = APIRouter()

_AUTH_TIMEOUT_SECONDS = 10.0


@router.websocket("/ws/hub")
async def hub_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    # ── 인증 (§5-1 auth) ──
    try:
        first = await asyncio.wait_for(websocket.receive_json(), timeout=_AUTH_TIMEOUT_SECONDS)
    except (TimeoutError, WebSocketDisconnect, RuntimeError, ValueError):
        # 타임아웃·즉시 종료·비JSON 첫 프레임 전부 인증 실패 취급
        await websocket.close(code=4401)
        return
    if not isinstance(first, dict) or first.get("type") != "auth":
        await websocket.send_json({"type": "auth.error", "code": "invalid_token"})
        await websocket.close(code=4401)
        return
    try:
        payload = decode_jwt(str(first.get("token", "")))
    except UnauthorizedError:
        await websocket.send_json({"type": "auth.error", "code": "invalid_token"})
        await websocket.close(code=4401)
        return

    hub_id = str(payload.get("sub", ""))
    async with get_session_factory()() as db:
        hub = await auth_crud.get_hub_by_hub_id(db, hub_id)
        room_slug: str | None = None
        if hub is not None and hub.room_id is not None:
            room = await db.get(Room, hub.room_id)
            room_slug = room.slug if room else None
    if hub is None:
        # 페어링 해제된 허브 — JWT가 남아 있어도 차단 (§11 토큰 폐기 = 즉시 차단)
        await websocket.send_json({"type": "auth.error", "code": "revoked"})
        await websocket.close(code=4401)
        return

    await websocket.send_json(
        {
            "type": "auth.ok",
            "hub_id": hub_id,
            "room": room_slug,
            "server_time": datetime.now(UTC).isoformat(),
        }
    )
    hub_manager.register(hub_id, websocket)
    handler = VoiceSessionHandler(websocket, hub_pk=hub.id, hub_id=hub_id, room=room_slug)

    try:
        while True:
            message = await websocket.receive()
            if message["type"] == "websocket.disconnect":
                break
            if message.get("text") is not None:
                await handler.handle_text(message["text"])
            elif message.get("bytes") is not None:
                await handler.handle_bytes(message["bytes"])
    except WebSocketDisconnect:
        pass
    finally:
        await handler.close()
        hub_manager.unregister(hub_id, websocket)
        logger.info("ws session closed: {}", hub_id)
