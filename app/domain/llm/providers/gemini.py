"""Gemini 프로필 — Google의 OpenAI 호환 엔드포인트 사용."""

from typing import ClassVar

from app.config import Settings
from app.core.exceptions import ProviderNotConfiguredError
from app.domain.llm.providers.openai_compat import OpenAICompatProvider
from app.domain.llm.providers.registry import llm_registry


@llm_registry.register("gemini")
class GeminiProvider(OpenAICompatProvider):
    name: ClassVar[str] = "gemini"

    @classmethod
    def from_settings(cls, settings: Settings) -> "GeminiProvider":
        if not settings.gemini_api_key:
            raise ProviderNotConfiguredError("GEMINI_API_KEY is not set")
        if not settings.llm_model:
            raise ProviderNotConfiguredError("LLM_MODEL is not set for provider 'gemini'")
        return cls(
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
            api_key=settings.gemini_api_key,
            model=settings.llm_model,
        )
