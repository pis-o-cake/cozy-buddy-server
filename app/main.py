"""FastAPI application entrypoint."""

import importlib
import pkgutil
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from loguru import logger

from app.config import settings
from app.core.database import Base, engine
from app.core.exceptions import CozyBuddyError
from app.core.logging import setup_logging
from app.domain.llm.service import LLMService
from app.domain.rag.service import RAGService
from app.middleware.error_handler import cozy_buddy_error_handler, global_error_handler
from app.middleware.request_logger import RequestLoggerMiddleware

llm_service = LLMService()
rag_service = RAGService()


def _register_domain_routers(application: FastAPI) -> None:
    """Auto-discover and register domain/*/api.py routers."""
    import app.domain as domain_pkg

    for module_info in pkgutil.iter_modules(domain_pkg.__path__):
        if not module_info.ispkg:
            continue

        domain_name = module_info.name
        module_path = f"app.domain.{domain_name}.api"

        try:
            module = importlib.import_module(module_path)
            router = getattr(module, "router", None)
            if router:
                application.include_router(
                    router,
                    prefix=f"/api/{domain_name}",
                    tags=[domain_name],
                )
                logger.info(f"Router registered: /api/{domain_name}")
        except ModuleNotFoundError:
            logger.debug(f"No router found: {domain_name} (api.py not exists)")


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    setup_logging()
    logger.info(f"{settings.app_name} v{settings.app_version} starting")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created")

    await llm_service.initialize()
    await rag_service.initialize()

    yield

    await rag_service.shutdown()
    await llm_service.shutdown()
    await engine.dispose()
    logger.info(f"{settings.app_name} shutdown")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(RequestLoggerMiddleware)
app.add_exception_handler(CozyBuddyError, cozy_buddy_error_handler)
app.add_exception_handler(Exception, global_error_handler)
_register_domain_routers(app)


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}
