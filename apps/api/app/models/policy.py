from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Severity


class Policy(Base):
    """A governance rule evaluated by the Policy Brain."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(160))

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity", values_callable=lambda e: [m.value for m in e])
    )

    evaluations_24h: Mapped[int] = mapped_column(Integer, default=0)
    violations_24h: Mapped[int] = mapped_column(Integer, default=0)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
