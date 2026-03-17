"""LLM adapter abstract base."""

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from app.domain.llm.schemas import LLMResponse


class LLMAdapter(ABC):
    """LLM provider interface."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize model/client."""

    @abstractmethod
    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Chat completion request."""

    @abstractmethod
    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat completion request."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Clean up resources."""
