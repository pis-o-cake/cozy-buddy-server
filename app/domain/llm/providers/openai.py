"""OpenAI 프로필 (OpenAI 호환 공통 베이스 사용)."""

from typing import ClassVar

from app.config import Settings
from app.core.exceptions import ProviderNotConfiguredError
from app.domain.llm.providers.openai_compat import OpenAICompatProvider
from app.domain.llm.providers.registry import llm_registry


@llm_registry.register("openai")
class OpenAIProvider(OpenAICompatProvider):
    name: ClassVar[str] = "openai"

    @classmethod
    def from_settings(cls, settings: Settings) -> "OpenAIProvider":
        if not settings.openai_api_key:
            raise ProviderNotConfiguredError("OPENAI_API_KEY is not set")
        if not settings.llm_model:
            raise ProviderNotConfiguredError("LLM_MODEL is not set for provider 'openai'")
        return cls(
            base_url="https://api.openai.com/v1",
            api_key=settings.openai_api_key,
            model=settings.llm_model,
        )
