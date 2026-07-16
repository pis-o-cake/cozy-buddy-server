"""도메인 LLM tool 자동 로더 (models_loader와 동일 패턴 — 설계서 §7-2).

`app/domain/*/llm_tools.py`를 import해 tool_registry 등록을 트리거한다.
도메인 추가 시 코어 수정 불필요.
"""

import importlib
import pkgutil

from app import domain


def import_all_tools() -> None:
    for module_info in pkgutil.iter_modules(domain.__path__):
        module_name = f"app.domain.{module_info.name}.llm_tools"
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            if exc.name == module_name:
                continue
            raise
