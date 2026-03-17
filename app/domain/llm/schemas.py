"""LLM domain schemas."""

from typing import Any

from pydantic import BaseModel, Field


class LLMRequest(BaseModel):
    """LLM request."""

    messages: list[dict[str, str]] = Field(..., description="Chat messages")
    tools: list[dict[str, Any]] | None = Field(default=None, description="Available tools")
    provider: str | None = Field(default=None, description="LLM provider (vllm/openai/gemini)")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1)


class LLMResponse(BaseModel):
    """LLM response."""

    content: str
    tool_calls: list[dict[str, Any]] | None = None
    usage: dict[str, int] | None = None
