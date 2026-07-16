"""TTSProvider 계약 (설계서 §3-2). 구현체(Supertonic 등)는 Phase 1."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import ClassVar


@dataclass
class AudioChunk:
    pcm: bytes
    rate: int = 24000
    is_last: bool = False


@dataclass
class TTSCapabilities:
    streaming: bool = False  # 진짜 스트리밍 합성 여부 (문장 단위 파이프라인과 별개)
    voices: list[str] = field(default_factory=list)


class TTSProvider(ABC):
    name: ClassVar[str] = ""

    @abstractmethod
    async def initialize(self) -> None: ...

    @abstractmethod
    def synthesize_stream(
        self, text: str, *, voice: str | None = None
    ) -> AsyncIterator[AudioChunk]:
        """문장 단위 입력 → 오디오 청크 스트림.

        비스트리밍 엔진도 문장별 합성→즉시 yield로 체감 지연을 최소화한다
        (파이프라인 규약 — 설계서 §4).
        """

    @abstractmethod
    def capabilities(self) -> TTSCapabilities: ...

    @abstractmethod
    async def shutdown(self) -> None: ...
