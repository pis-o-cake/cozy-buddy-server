"""chat 도메인 모델 (설계서 §6-2 CHAT_SESSION·MESSAGE).

세션 키는 hub_id — 거실·침실 동시 대화 독립 (설계서 §7-4). 세션 서비스는 Phase 1.
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import JSON_VARIANT, Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True)
    hub_id: Mapped[int] = mapped_column(sa.ForeignKey("hubs.id"))
    user_id: Mapped[int | None] = mapped_column(sa.ForeignKey("users.id"), nullable=True)
    summary: Mapped[str | None] = mapped_column(sa.Text, nullable=True)  # 롤링 요약 (§7-4)
    last_active_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())  # 3분 만료 판정
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    session_id: Mapped[int] = mapped_column(sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(sa.String(20))  # user | assistant | tool
    content: Mapped[str] = mapped_column(sa.Text)
    tool_calls: Mapped[list[Any] | None] = mapped_column(JSON_VARIANT, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=sa.func.now())
