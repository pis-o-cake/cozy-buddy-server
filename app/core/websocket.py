"""허브 WS 연결 관리 (설계서 §4-3 — 허브당 영속 연결 1개)."""

from fastapi import WebSocket
from loguru import logger


class HubConnectionManager:
    """hub_id → WebSocket 매핑. 서버 발신 push(timer.fired, broadcast 등 §5-1)의 진입점."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}

    def register(self, hub_id: str, websocket: WebSocket) -> None:
        # 재연결 시 기존 소켓은 신규로 대체 (허브당 1연결 — §4-3)
        self._connections[hub_id] = websocket
        logger.info("hub connected: {} (total={})", hub_id, len(self._connections))

    def unregister(self, hub_id: str, websocket: WebSocket) -> None:
        if self._connections.get(hub_id) is websocket:
            del self._connections[hub_id]
            logger.info("hub disconnected: {} (total={})", hub_id, len(self._connections))

    def get(self, hub_id: str) -> WebSocket | None:
        return self._connections.get(hub_id)

    def connected_hub_ids(self) -> list[str]:
        return sorted(self._connections)

    async def send_to(self, hub_id: str, payload: dict) -> bool:
        """특정 허브로 서버 발신 push (§5-1 timer.fired·broadcast 등). 미연결이면 False."""
        websocket = self._connections.get(hub_id)
        if websocket is None:
            return False
        try:
            await websocket.send_json(payload)
            return True
        except Exception as exc:
            logger.warning("push to hub {} failed: {}", hub_id, exc)
            return False

    async def broadcast_all(self, payload: dict) -> None:
        """전 허브 push — device.state_changed 대시보드 실시간 갱신용 (§5-1)."""
        for hub_id in list(self._connections):
            await self.send_to(hub_id, payload)


hub_manager = HubConnectionManager()
