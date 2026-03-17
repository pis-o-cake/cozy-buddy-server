"""Chat domain API router."""

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session, get_db
from app.core.websocket import ws_manager
from app.domain.chat import crud
from app.domain.chat.schemas import ChatMessageRequest, ChatMessageResponse
from app.domain.chat.service import ChatService

router = APIRouter()


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatMessageResponse:
    """Send text message and get AI response."""
    service = ChatService(db)
    assistant_msg = await service.process_message(
        content=request.content,
        provider=request.provider,
    )
    return ChatMessageResponse.model_validate(assistant_msg)


@router.get("/history", response_model=list[ChatMessageResponse])
async def get_history(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageResponse]:
    """Get conversation history."""
    messages = await crud.get_recent_messages(db, limit=limit)
    return [ChatMessageResponse.model_validate(m) for m in messages]


@router.delete("/history")
async def clear_history(
    db: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    """Clear all conversation history."""
    deleted = await crud.clear_messages(db)
    return {"deleted": deleted}


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming chat.

    Client sends: {"content": "...", "provider": "openai"}
    Server sends: {"type": "chunk", "content": "..."} per token
    Server sends: {"type": "done"} when complete
    Server sends: {"type": "error", "message": "..."} on error
    """
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            content = data.get("content", "")
            provider = data.get("provider")

            if not content:
                await ws_manager.send_json(websocket, {
                    "type": "error", "message": "Empty content",
                })
                continue

            async with async_session() as db:
                service = ChatService(db)
                try:
                    async for chunk in service.process_message_stream(
                        content=content, provider=provider
                    ):
                        await ws_manager.send_json(websocket, {
                            "type": "chunk", "content": chunk,
                        })
                    await ws_manager.send_json(websocket, {"type": "done"})
                    await db.commit()
                except Exception as e:
                    logger.error(f"WebSocket chat error: {e}")
                    await ws_manager.send_json(websocket, {
                        "type": "error", "message": str(e),
                    })
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
