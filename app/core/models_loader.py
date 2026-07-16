"""도메인 모델 자동 로더.

`app/domain/*/models.py`를 전부 import해 `Base.metadata`를 완성한다.
Alembic autogenerate·테이블 생성이 이 함수 하나에 의존 — 도메인 추가 시 코어 수정 불필요.
"""

import importlib
import pkgutil

from app import domain


def import_all_models() -> None:
    for module_info in pkgutil.iter_modules(domain.__path__):
        module_name = f"app.domain.{module_info.name}.models"
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as exc:
            # models.py가 없는 도메인(voice 등)은 정상 — 그 외 import 오류는 전파
            if exc.name == module_name:
                continue
            raise
