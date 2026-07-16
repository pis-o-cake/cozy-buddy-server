"""LLM 팩토리 — 키 기반 자동 선택·자동 비활성 정책 (설계서 §7-5)."""

import pytest

from app.core.exceptions import ProviderNotConfiguredError, ProviderNotFoundError
from app.domain.llm.factory import available_llm_providers, build_llm
from app.domain.llm.providers.anthropic import AnthropicProvider
from app.domain.llm.providers.gemini import GeminiProvider
from tests.conftest import make_settings


def test_no_keys_raises_not_configured():
    with pytest.raises(ProviderNotConfiguredError):
        build_llm(make_settings())


def test_auto_selects_configured_provider():
    settings = make_settings(anthropic_api_key="sk-test")
    provider = build_llm(settings)
    assert isinstance(provider, AnthropicProvider)


def test_cloud_priority_order():
    # gemini와 anthropic 둘 다 구성 → 우선순위(gemini)가 선택된다
    settings = make_settings(gemini_api_key="g-test", anthropic_api_key="sk-test", llm_model="m")
    provider = build_llm(settings)
    assert isinstance(provider, GeminiProvider)


def test_explicit_provider_without_key_fails():
    settings = make_settings(llm_provider="openai")
    with pytest.raises(ProviderNotConfiguredError):
        build_llm(settings)


def test_openai_compat_requires_model():
    settings = make_settings(llm_provider="gemini", gemini_api_key="g-test")
    with pytest.raises(ProviderNotConfiguredError):
        build_llm(settings)


def test_unknown_provider_raises():
    settings = make_settings(llm_provider="hal9000")
    with pytest.raises(ProviderNotFoundError):
        build_llm(settings)


def test_available_flags_reflect_keys():
    flags = available_llm_providers(make_settings(openai_api_key="o-test"))
    assert flags["openai"] is True
    assert flags["gemini"] is False
    assert flags["anthropic"] is False
    assert flags["llamacpp"] is True  # 로컬 — 키 불필요 (자동 선택 대상은 아님)
