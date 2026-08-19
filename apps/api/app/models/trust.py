from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.agent import Agent


class TrustSnapshot(Base):
    """A trust score as computed at a point in time.

    Agents carry their latest score for fast reads; this table is the history
    that makes trend, drift, and forecasting possible. Without it a "trust
    trend" can only be faked.
    """

    __tablename__ = "trust_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )

    score: Mapped[int] = mapped_column(Integer)
    # Weighted mean of the factors, before anomaly penalties.
    base_score: Mapped[float] = mapped_column(Float)
    # Points deducted for recent blocked/escalated decisions.
    anomaly_penalty: Mapped[float] = mapped_column(Float, default=0.0)

    # Factor scores as they stood at capture time, so a historical score can be
    # explained even after the agent's current factors have moved on.
    factors: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)

    # What triggered this evaluation, e.g. "recompute", "post-decision", "seed".
    reason: Mapped[str] = mapped_column(String(40), default="recompute")

    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, server_default=func.now()
    )

    agent: Mapped["Agent"] = relationship(back_populates="snapshots")
