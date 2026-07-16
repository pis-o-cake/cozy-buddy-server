"""사용자 대면 문구 언어팩 (설계서 §7 로컬라이제이션 규칙).

`app/locales/<locale>.json`의 중첩 키를 점 표기("errors.unauthorized")로 조회한다.
로그·내부 예외에는 사용하지 않는다 — 그쪽은 영어 하드코딩.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config import get_settings

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


@lru_cache
def _load(locale: str) -> dict[str, Any]:
    path = _LOCALES_DIR / f"{locale}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def t(key: str, locale: str | None = None, **params: Any) -> str:
    """언어팩에서 문구를 찾아 포맷한다. 키가 없으면 키 자체를 반환(누락 가시화).

    Args:
        key: 점 표기 중첩 키. 예) "errors.unauthorized".
        locale: 미지정 시 설정의 default_locale.
        **params: str.format 파라미터.
    """
    loc = locale or get_settings().default_locale
    node: Any = _load(loc)
    for part in key.split("."):
        if not isinstance(node, dict) or part not in node:
            return key
        node = node[part]
    if not isinstance(node, str):
        return key
    return node.format(**params) if params else node
