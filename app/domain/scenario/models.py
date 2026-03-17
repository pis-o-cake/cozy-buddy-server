"""Scenario domain DB model."""

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Scenario(Base):
    """Scenario model."""

    __tablename__ = "scenarios"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    actions: Mapped[list] = mapped_column(JSON, nullable=False)
    trigger: Mapped[str] = mapped_column(String(20), default="manual")
