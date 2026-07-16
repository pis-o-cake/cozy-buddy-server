"""LLM 토큰 스트림 → 문장 단위 분리 (설계서 §4 TTS 파이프라인 규약).

첫 문장이 완성되는 즉시 TTS로 넘겨 체감 지연을 최소화한다.
"""

import re

_SENTENCE_END = re.compile(r"[.!?…]+[\s\"']*|\n+")
_MIN_SENTENCE_CHARS = 2


class SentenceSplitter:
    """스트리밍 텍스트를 문장 경계에서 잘라낸다."""

    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        """조각을 누적하고, 완성된 문장들을 반환한다."""
        self._buffer += text
        sentences: list[str] = []
        while True:
            match = _SENTENCE_END.search(self._buffer)
            if match is None:
                break
            candidate = self._buffer[: match.end()].strip()
            self._buffer = self._buffer[match.end() :]
            if len(candidate) >= _MIN_SENTENCE_CHARS:
                sentences.append(candidate)
        return sentences

    def flush(self) -> str | None:
        """스트림 종료 시 남은 조각을 반환한다."""
        remainder = self._buffer.strip()
        self._buffer = ""
        return remainder if len(remainder) >= _MIN_SENTENCE_CHARS else None
