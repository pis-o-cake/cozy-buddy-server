"""공용 픽스처 — 단위 테스트는 SQLite in-memory (통합 테스트는 PostgreSQL 컨테이너 기준, §6-2)."""

import os

os.environ.setdefault("JWT_SECRET", "test-secret-0123456789abcdef0123456789abcdef")

import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import tests.fakes  # noqa: F401 — fake provider 등록
from app.config import Settings
from app.core.database import Base, get_session
from app.core.models_loader import import_all_models


def make_settings(**overrides: object) -> Settings:
    """env/.env 영향 없이 순수 기본값으로 Settings를 만든다 (단위 테스트 격리용)."""
    settings = Settings.model_construct()
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


@pytest.fixture
async def db_engine():
    import_all_models()
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def client(db_engine):
    from app.main import app

    session_factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def override_session():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as async_client:
        yield async_client
    app.dependency_overrides.clear()
