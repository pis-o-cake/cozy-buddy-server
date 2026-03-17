"""Internationalization support."""

import json
from pathlib import Path
from typing import Any

_LOCALES_DIR = Path(__file__).parent.parent / "locales"
_messages: dict[str, Any] = {}


def _load_locale(locale: str = "ko") -> dict[str, Any]:
    path = _LOCALES_DIR / f"{locale}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def t(key: str, locale: str = "ko", **kwargs: Any) -> str:
    """Translate message key to localized string.

    key: dot-separated path (e.g. "error.internal")
    """
    global _messages
    if locale not in _messages:
        _messages[locale] = _load_locale(locale)

    parts = key.split(".")
    value: Any = _messages[locale]
    for part in parts:
        if not isinstance(value, dict):
            return key
        value = value.get(part)
        if value is None:
            return key

    if not isinstance(value, str):
        return key

    if kwargs:
        return value.format(**kwargs)
    return value
