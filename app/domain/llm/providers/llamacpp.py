"""llama.cpp llama-server 프로필 — Phase 4+ 로컬 LLM 슬롯 (설계서 §14-2, v3.3).

llama-server는 OpenAI 호환 API를 제공하므로 공통 베이스를 그대로 사용한다.
v1(클라우드 우선)에서는 명시적으로 `LLM_PROVIDER=llamacpp`를 지정한 경우에만 선택된다.
"""

from typing import ClassVar

from app.config import Settings
from app.domain.llm.providers.openai_compat import OpenAICompatProvider
from app.domain.llm.providers.registry import llm_registry


@llm_registry.register("llamacpp")
class LlamaCppProvider(OpenAICompatProvider):
    name: ClassVar[str] = "llamacpp"

    @classmethod
    def from_settings(cls, settings: Settings) -> "LlamaCppProvider":
        # 로컬 서버는 API 키 불필요. 모델은 llama-server에 적재된 것을 사용.
        return cls(
            base_url=settings.llamacpp_base_url,
            api_key="",
            model=settings.llm_model or "local",
        )
