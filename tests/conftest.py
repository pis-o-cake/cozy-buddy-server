"""테스트 공통 설정."""

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
async_test_session = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest_asyncio.fixture
async def db_session():
    """테스트용 DB 세션."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_test_session() as session:
        yield session

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """테스트용 HTTP 클라이언트."""
    from httpx import ASGITransport, AsyncClient

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def tmp_dir():
    """임시 디렉토리 (RAG 테스트 등)."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as d:
        yield Path(d)
