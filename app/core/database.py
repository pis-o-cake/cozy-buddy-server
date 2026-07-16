"""비동기 DB 계층 (설계서 §6-2 — PostgreSQL 16 기본, SQLite는 개발/단위테스트 슬롯).

JSON 컬럼은 `JSON_VARIANT`를 사용한다: PostgreSQL에서는 JSONB, 그 외(SQLite)에서는 JSON으로
컴파일되어 단위 테스트와 운영 DB를 같은 모델로 커버한다.
"""

from collections.abc import AsyncIterator

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

JSON_VARIANT = sa.JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    """전 도메인 공용 declarative base. Alembic metadata의 단일 출처."""


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(settings.database_url, echo=settings.debug)
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _session_factory


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI `Depends()`용 세션 의존성. 요청 단위로 열고 닫는다."""
    async with get_session_factory()() as session:
        yield session
