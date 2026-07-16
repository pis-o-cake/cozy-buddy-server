"""auth 도메인 모델 (설계서 §6-2 USER·HUB).

Hub는 페어링(§11)의 산물이므로 auth 도메인이 소유한다. room 배정은 device 도메인의
Room을 FK로 참조만 한다.
"""

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    """가구 구성원. v1은 단일 가구 가정 — 화자 구분 대비 필드만 선반영 (설계서 §6-2)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    role: Mapped[str] = mapped_column(sa.String(20), default="member")  # admin | member
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())


class Hub(Base):
    """페어링된 Android 태블릿 허브. token_hash로만 대조 — 평문 미저장 (설계서 §11)."""

    __tablename__ = "hubs"

    id: Mapped[int] = mapped_column(primary_key=True)
    hub_id: Mapped[str] = mapped_column(sa.String(64), unique=True)  # 예: "living-01"
    room_id: Mapped[int | None] = mapped_column(sa.ForeignKey("rooms.id"), nullable=True)
    name: Mapped[str] = mapped_column(sa.String(100))
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    paired_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(nullable=True)
