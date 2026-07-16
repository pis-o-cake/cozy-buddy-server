"""scenario 도메인 모델 (설계서 §6-2 SCENARIO·SCENARIO_ACTION).

기기 참조는 device_id FK가 정본 — 자연어 지칭은 등록/편집 시점에 해석해 정규화한다
(설계서 §9-2). 실행 엔진·스케줄러는 Phase 2.
"""

from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import JSON_VARIANT, Base


class Scenario(Base):
    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(100), unique=True)  # 예: "굿모닝"
    triggers: Mapped[list[Any]] = mapped_column(JSON_VARIANT, default=list)  # §9-1 트리거 배열
    enabled: Mapped[bool] = mapped_column(default=True)


class ScenarioAction(Base):
    __tablename__ = "scenario_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    scenario_id: Mapped[int] = mapped_column(sa.ForeignKey("scenarios.id", ondelete="CASCADE"))
    order: Mapped[int] = mapped_column()  # 실행 순서
    parallel_group: Mapped[int | None] = mapped_column(nullable=True)  # 동일 그룹 = 병렬 (§9-2)
    device_id: Mapped[int | None] = mapped_column(sa.ForeignKey("devices.id"), nullable=True)
    command: Mapped[dict[str, Any]] = mapped_column(JSON_VARIANT)  # 타입별 스키마 (§9-2)
