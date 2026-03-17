"""Google Gemini adapter."""

from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from app.domain.llm.adapters.base import LLMAdapter
from app.domain.llm.schemas import LLMResponse


class GeminiAdapter(LLMAdapter):
    """Google Gemini API adapter (OpenAI compatible mode)."""

    GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

    def __init__(self, *, api_key: str, model: str = "gemini-2.5-flash") -> None:
        self._api_key = api_key
        self._model = model
        self._client: Any = None

    async def initialize(self) -> None:
        """Initialize Gemini client (OpenAI compatible)."""
        from openai import AsyncOpenAI

        self._client = AsyncOpenAI(
            base_url=self.GEMINI_BASE_URL,
            api_key=self._api_key,
        )
        logger.info(f"Gemini adapter initialized: model={self._model}")

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        """Chat completion request."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in choice.message.tool_calls
            ]

        return LLMResponse(
            content=choice.message.content or "",
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else None,
        )

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        if tools:
            kwargs["tools"] = tools

        stream = await self._client.chat.completions.create(**kwargs)
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def shutdown(self) -> None:
        """Clean up client."""
        if self._client:
            await self._client.close()
            logger.info("Gemini adapter shutdown")
