"""범용 Provider 레지스트리 (설계서 §3-2).

새 구현 추가 = 클래스 1개 + `@registry.register("name")` 1줄 + `.env` 변경 — 코어 무수정.
STT/TTS/LLM/IoT 어댑터가 모두 이 패턴을 공유한다.
"""

from collections.abc import Callable
from typing import Any

from app.core.exceptions import ProviderNotFoundError


class ProviderRegistry[T]:
    """도메인별 provider 등록/생성.

    Example:
        stt_registry: ProviderRegistry[STTProvider] = ProviderRegistry("stt")

        @stt_registry.register("faster-whisper")
        class FasterWhisperSTT(STTProvider): ...

        provider = stt_registry.build(settings.stt_provider)
    """

    def __init__(self, kind: str) -> None:
        self._kind = kind
        self._entries: dict[str, type[T]] = {}

    @property
    def kind(self) -> str:
        return self._kind

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        """클래스 데코레이터로 provider를 등록한다. 이름 중복은 프로그래밍 오류로 즉시 실패."""

        def decorator(cls: type[T]) -> type[T]:
            if name in self._entries:
                raise ValueError(f"{self._kind} provider '{name}' already registered")
            self._entries[name] = cls
            return cls

        return decorator

    def names(self) -> list[str]:
        return sorted(self._entries)

    def get(self, name: str) -> type[T]:
        if name not in self._entries:
            raise ProviderNotFoundError(self._kind, name, self.names())
        return self._entries[name]

    def build(self, name: str, **kwargs: Any) -> T:
        """등록된 클래스를 인스턴스화한다. 미등록 이름이면 ProviderNotFoundError."""
        return self.get(name)(**kwargs)
