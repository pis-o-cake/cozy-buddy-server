"""WebSocket connection manager."""

from fastapi import WebSocket
from loguru import logger


class WebSocketManager:
    """WebSocket connection management."""

    def __init__(self) -> None:
        self._connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        """Accept client connection."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.info(f"WebSocket connected ({len(self._connections)} active)")

    async def disconnect(self, websocket: WebSocket) -> None:
        """Remove client connection."""
        self._connections.remove(websocket)
        logger.info(f"WebSocket disconnected ({len(self._connections)} active)")

    async def send_json(self, websocket: WebSocket, data: dict) -> None:
        """Send JSON message."""
        await websocket.send_json(data)

    async def send_bytes(self, websocket: WebSocket, data: bytes) -> None:
        """Send binary data (audio, etc.)."""
        await websocket.send_bytes(data)

    async def broadcast_json(self, data: dict) -> None:
        """Broadcast JSON to all clients."""
        for connection in self._connections:
            try:
                await connection.send_json(data)
            except Exception:
                logger.warning("Broadcast failed, removing connection")
                await self.disconnect(connection)


ws_manager = WebSocketManager()
