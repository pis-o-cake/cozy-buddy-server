"""FastAPI 앱 엔트리포인트.

라우터 자동등록: `app/domain/*/api.py`의 `router`를 `/api/<domain>`으로 마운트한다 —
도메인 추가 시 이 파일 수정 불필요 (설계서 §6-1 P6).
"""

import importlib
import pkgutil
from contextlib import asynccontextmanager

from fastapi import FastAPI
from loguru import logger

from app import domain
from app.config import get_settings
from app.core.logging import setup_logging
from app.core.models_loader import import_all_models
from app.domain.llm.factory import available_llm_providers
from app.middleware.error_handler import register_exception_handlers
from app.middleware.request_logger import register_request_logger


def _import_domain_module(name: str):
    try:
        return importlib.import_module(name)
    except ModuleNotFoundError as exc:
        if exc.name == name:  # 해당 모듈이 없는 도메인은 스킵
            return None
        raise


def _register_domain_routers(app: FastAPI) -> None:
    for module_info in pkgutil.iter_modules(domain.__path__):
        # REST: domain/<name>/api.py → /api/<name> 프리픽스
        module = _import_domain_module(f"app.domain.{module_info.name}.api")
        if module is not None and getattr(module, "router", None) is not None:
            app.include_router(module.router, prefix=f"/api/{module_info.name}")
            logger.info("router mounted: /api/{}", module_info.name)
        # WS: domain/<name>/ws.py → 프리픽스 없음 (경로는 모듈이 소유 — §5 /ws/hub)
        ws_module = _import_domain_module(f"app.domain.{module_info.name}.ws")
        if ws_module is not None and getattr(ws_module, "router", None) is not None:
            app.include_router(ws_module.router)
            logger.info("ws router mounted: {}", module_info.name)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    import_all_models()
    logger.info("{} starting (debug={})", settings.app_name, settings.debug)
    # Phase 1: STT/TTS provider warm-up이 여기 추가된다 (cold load 회피 — §13-2)
    yield
    logger.info("{} shutting down", settings.app_name)


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)

    register_request_logger(app)
    register_exception_handlers(app)
    _register_domain_routers(app)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        """liveness 체크 (NSSM 감시 연동 — 설계서 §13-3)."""
        return {"status": "ok"}

    @app.get("/api/system/status", tags=["system"])
    async def system_status() -> dict[str, object]:
        """provider 구성 현황. 키 값은 절대 노출하지 않는다 — 구성 여부(bool)만 (§11)."""
        return {
            "app": settings.app_name,
            "llm_providers": available_llm_providers(settings),
            "stt_provider": settings.stt_provider,
            "tts_provider": settings.tts_provider,
        }

    return app


app = create_app()
