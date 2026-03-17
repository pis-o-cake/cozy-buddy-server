"""Chat domain schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChatMessageRequest(BaseModel):
    """Chat message request."""

    content: str = Field(..., min_length=1, description="Message content")
    provider: str | None = Field(default=None, description="LLM provider (vllm/openai/gemini)")


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: int
    role: str
    content: str
    tool_call: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
