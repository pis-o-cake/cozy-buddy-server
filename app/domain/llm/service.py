"""LLM domain service."""

from collections.abc import AsyncGenerator
from typing import Any

from loguru import logger

from app.config import settings
from app.core.exceptions import LLMError
from app.domain.llm.adapters.base import LLMAdapter
from app.domain.llm.adapters.gemini import GeminiAdapter
from app.domain.llm.adapters.openai import OpenAIAdapter
from app.domain.llm.adapters.vllm import VLLMAdapter
from app.domain.llm.schemas import LLMResponse


class LLMService:
    """LLM call service (multi-provider)."""

    def __init__(self) -> None:
        self._adapters: dict[str, LLMAdapter] = {}

    async def initialize(self) -> None:
        """Initialize all configured provider adapters."""
        adapter_configs: list[tuple[str, LLMAdapter | None]] = [
            ("vllm", VLLMAdapter(
                base_url=settings.vllm_base_url,
                model=settings.vllm_model,
                api_key=settings.vllm_api_key,
            )),
            ("openai", OpenAIAdapter(
                api_key=settings.openai_api_key,
                model=settings.openai_model,
            ) if settings.openai_api_key else None),
            ("gemini", GeminiAdapter(
                api_key=settings.gemini_api_key,
                model=settings.gemini_model,
            ) if settings.gemini_api_key else None),
        ]

        for name, adapter in adapter_configs:
            if not adapter:
                continue
            try:
                await adapter.initialize()
                self._adapters[name] = adapter
                logger.info(f"LLM adapter initialized: {name}")
            except Exception:
                logger.warning(f"LLM adapter init failed (skipped): {name}")

        if not self._adapters:
            logger.warning("No active LLM adapters")

    def get_available_providers(self) -> list[str]:
        """Get list of available providers."""
        return list(self._adapters.keys())

    def _get_adapter(self, provider: str | None = None) -> LLMAdapter:
        """Get specified or default adapter."""
        target = provider or settings.llm_default_provider

        adapter = self._adapters.get(target)
        if not adapter:
            available = ", ".join(self._adapters.keys()) or "none"
            raise LLMError(
                message=f"Provider '{target}' unavailable (active: {available})"
            )
        return adapter

    async def chat(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        provider: str | None = None,
    ) -> LLMResponse:
        """Chat completion request."""
        adapter = self._get_adapter(provider)
        logger.info(f"LLM request: provider={provider or settings.llm_default_provider}, {len(messages)} messages")
        return await adapter.chat(
            messages=messages,
            tools=tools,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )

    async def chat_stream(
        self,
        *,
        messages: list[dict[str, str]],
        tools: list[dict[str, Any]] | None = None,
        provider: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """Streaming chat."""
        adapter = self._get_adapter(provider)
        logger.info(f"LLM streaming: provider={provider or settings.llm_default_provider}, {len(messages)} messages")
        async for chunk in adapter.chat_stream(
            messages=messages,
            tools=tools,
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        ):
            yield chunk

    async def shutdown(self) -> None:
        """Shutdown all adapters."""
        for name, adapter in self._adapters.items():
            await adapter.shutdown()
            logger.info(f"LLM adapter shutdown: {name}")
        self._adapters.clear()
