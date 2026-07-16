"""device 도메인 모델 (설계서 §6-2 ROOM·DEVICE).

device_type(용도)·adapter_type(제어 방식)·capabilities를 분리해 브랜드 무관 편입을
보장한다 (설계서 §8-1 taxonomy). 서비스/어댑터 구현은 Phase 2.
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import JSON_VARIANT, Base


class Room(Base):
    """방 — 멀티룸 해석(설계서 §8-3)의 기준 단위."""

    __tablename__ = "rooms"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))  # 예: "거실"
    slug: Mapped[str] = mapped_column(sa.String(50), unique=True)  # 예: "living"


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100))  # 예: "거실 스탠드"
    room_id: Mapped[int] = mapped_column(sa.ForeignKey("rooms.id"))
    device_type: Mapped[str] = mapped_column(sa.String(30))  # taxonomy 키 (§8-1)
    adapter_type: Mapped[str] = mapped_column(sa.String(30))  # kasa | matter | ...
    capabilities: Mapped[list[Any]] = mapped_column(JSON_VARIANT, default=list)
    config: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT, default=dict)  # 어댑터별 (host 등)
    online: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
