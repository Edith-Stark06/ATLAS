from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import DecisionOutcome

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.simulation import SimulationRun


class Decision(Base):
    """A single governed action, recorded after the pipeline reached a verdict."""

    __tablename__ = "decisions"

    # Transaction reference from the originating enterprise system.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    agent_id: Mapped[str] = mapped_column(String(64), ForeignKey("agents.id"), index=True)

    action: Mapped[str] = mapped_column(String(300))
    # Money is Numeric, never float — 12,450.00 must round-trip exactly.
    amount_usd: Mapped[Decimal | None] = mapped_column(Numeric(16, 2), nullable=True)

    outcome: Mapped[DecisionOutcome] = mapped_column(
        Enum(
            DecisionOutcome, name="decision_outcome", values_callable=lambda e: [m.value for m in e]
        ),
        index=True,
    )

    trust_score: Mapped[int] = mapped_column(Integer)
    risk_score: Mapped[int] = mapped_column(Integer)

    decided_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    latency_ms: Mapped[int] = mapped_column(Integer)
    rationale: Mapped[str] = mapped_column(Text)

    # Variable-shape payload (critical factors, risk vector, trace). Relational
    # columns would mean several sparse tables for data that is always read as
    # one blob alongside its decision.
    investigation: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    agent: Mapped["Agent"] = relationship(back_populates="decisions", lazy="joined")

    @property
    def agent_name(self) -> str:
        """Convenience for serialisation — the console lists decisions by agent."""
        return self.agent.name if self.agent else ""

    policy_checks: Mapped[list["PolicyCheck"]] = relationship(
        back_populates="decision",
        cascade="all, delete-orphan",
        order_by="PolicyCheck.id",
        lazy="selectin",
    )
    simulations: Mapped[list["SimulationRun"]] = relationship(back_populates="decision")


class PolicyCheck(Base):
    """Outcome of evaluating one policy against one decision.

    `policy_name` is denormalised on purpose: policies are versioned and
    renamed over time, and an audit record must show the name as it was when
    the decision was made.
    """

    __tablename__ = "policy_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    decision_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("decisions.id", ondelete="CASCADE"), index=True
    )
    policy_id: Mapped[str] = mapped_column(String(64), index=True)
    policy_name: Mapped[str] = mapped_column(String(200))

    passed: Mapped[bool] = mapped_column(Boolean)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)

    decision: Mapped[Decision] = relationship(back_populates="policy_checks")
