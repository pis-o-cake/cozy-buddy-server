"""LLM provider 팩토리 (설계서 §7-5).

- `LLM_PROVIDER` 미지정 시 키가 구성된 클라우드 provider를 우선순위대로 자동 선택.
- 키 없는 provider는 후보에서 자동 제외, 명시 선택 시엔 명확한 오류 (§7-5 API 키 정책).
- llamacpp(로컬)는 자동 선택 대상이 아님 — 명시 지정 시에만 (v3.3 클라우드 우선).
"""

from loguru import logger

# 어댑터 등록 트리거 — 새 provider 추가 시 여기에 import 한 줄
import app.domain.llm.providers.anthropic  # noqa: F401
import app.domain.llm.providers.gemini  # noqa: F401
import app.domain.llm.providers.llamacpp  # noqa: F401
import app.domain.llm.providers.openai  # noqa: F401
from app.config import Settings, get_settings
from app.core.exceptions import ProviderNotConfiguredError
from app.domain.llm.providers.base import LLMProvider
from app.domain.llm.providers.registry import llm_registry

_CLOUD_PRIORITY = ("gemini", "openai", "anthropic")


def _has_key(name: str, settings: Settings) -> bool:
    match name:
        case "gemini":
            return bool(settings.gemini_api_key)
        case "openai":
            return bool(settings.openai_api_key)
        case "anthropic":
            return bool(settings.anthropic_api_key)
        case "llamacpp":
            return True  # 로컬 — 키 불필요 (단, 자동 선택 대상 아님)
        case _:
            return False


def available_llm_providers(settings: Settings | None = None) -> dict[str, bool]:
    """provider별 구성 여부. `/api/system/status` 노출용 — 키 값 자체는 절대 노출 금지 (§11)."""
    settings = settings or get_settings()
    return {name: _has_key(name, settings) for name in llm_registry.names()}


def build_llm(settings: Settings | None = None) -> LLMProvider:
    """활성 LLM provider를 조립한다.

    Raises:
        ProviderNotConfiguredError: 명시 provider의 키 누락, 또는 구성된 provider 전무.
        ProviderNotFoundError: 레지스트리에 없는 이름.
    """
    settings = settings or get_settings()

    name = settings.llm_provider
    if not name:
        name = next((n for n in _CLOUD_PRIORITY if _has_key(n, settings)), "")
    if not name:
        raise ProviderNotConfiguredError(
            "no llm provider configured (set LLM_PROVIDER or a cloud *_API_KEY)"
        )

    provider = llm_registry.get(name).from_settings(settings)
    logger.info("llm provider selected: {}", name)
    return provider
