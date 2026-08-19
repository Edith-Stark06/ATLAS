from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DecisionOutcome

if TYPE_CHECKING:
    from app.models.decision import Decision


class SimulationRun(Base):
    """One pre-execution simulation of a requested action."""

    __tablename__ = "simulation_runs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )

    scenario: Mapped[str] = mapped_column(String(300))
    agent_name: Mapped[str] = mapped_column(String(200))
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)
    trust_score: Mapped[int] = mapped_column(Integer)
    confidence: Mapped[float] = mapped_column(Float)

    recommendation: Mapped[DecisionOutcome] = mapped_column(
        Enum(
            DecisionOutcome,
            name="decision_outcome",
            values_callable=lambda e: [m.value for m in e],
            create_type=False,
        )
    )

    ran_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    duration_ms: Mapped[int] = mapped_column(Integer)

    # Ordered label/value rows describing the incoming request. Shape varies by
    # action type (a booking and a settlement expose different fields).
    request: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    decision: Mapped["Decision"] = relationship(back_populates="simulations")
    outcomes: Mapped[list["SimulationOutcome"]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="SimulationOutcome.id",
        lazy="selectin",
    )


class SimulationOutcome(Base):
    """One predicted future from a simulation run."""

    __tablename__ = "simulation_outcomes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("simulation_runs.id", ondelete="CASCADE"), index=True
    )

    label: Mapped[str] = mapped_column(String(160))
    probability: Mapped[float] = mapped_column(Float)
    financial_impact_usd: Mapped[Decimal] = mapped_column(Numeric(16, 2), default=0)
    risk_score: Mapped[int] = mapped_column(Integer)
    compliant: Mapped[bool] = mapped_column(Boolean)

    customer_experience: Mapped[str | None] = mapped_column(String(20), nullable=True)
    compliance_risk: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recommended: Mapped[bool] = mapped_column(Boolean, default=False)

    run: Mapped[SimulationRun] = relationship(back_populates="outcomes")
