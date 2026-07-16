"""timer 도메인 모델 (설계서 §6-2 TIMER).

타이머/알람/리마인더 공용. 발화 시 대상 허브로 `timer.fired` push (설계서 §5-1).
스케줄러 연동은 Phase 2.
"""

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import JSON_VARIANT, Base


class Timer(Base):
    __tablename__ = "timers"

    id: Mapped[int] = mapped_column(primary_key=True)
    hub_id: Mapped[int] = mapped_column(sa.ForeignKey("hubs.id"))  # 울릴 허브
    kind: Mapped[str] = mapped_column(sa.String(20))  # timer | alarm | reminder
    label: Mapped[str | None] = mapped_column(sa.String(200), nullable=True)
    fires_at: Mapped[datetime] = mapped_column()
    recurrence: Mapped[dict[str, Any] | None] = mapped_column(JSON_VARIANT, nullable=True)  # cron
    sunrise: Mapped[bool] = mapped_column(default=False)  # 선라이즈 연출 여부 (§2-4)
