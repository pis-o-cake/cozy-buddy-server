"""LLM provider 레지스트리 인스턴스 (순환 import 방지를 위해 독립 모듈)."""

from app.core.registry import ProviderRegistry
from app.domain.llm.providers.base import LLMProvider

llm_registry: ProviderRegistry[LLMProvider] = ProviderRegistry("llm")
