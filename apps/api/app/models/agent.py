from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import LifecycleState

if TYPE_CHECKING:
    from app.models.decision import Decision


class Agent(Base):
    """An autonomous agent registered with ATLAS.

    The primary key is the externally-meaningful agent identifier
    (e.g. "agt-travel-01") rather than a surrogate — these IDs are assigned
    by the registering system and appear throughout the console and ledger.
    """

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    capability: Mapped[str] = mapped_column(String(120))
    owner: Mapped[str] = mapped_column(String(120))

    lifecycle: Mapped[LifecycleState] = mapped_column(
        Enum(
            LifecycleState, name="lifecycle_state", values_callable=lambda e: [m.value for m in e]
        ),
        default=LifecycleState.ONBOARDING,
    )

    trust_score: Mapped[int] = mapped_column(Integer)
    trust_delta: Mapped[float] = mapped_column(Float, default=0.0)
    decisions_today: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    model: Mapped[str] = mapped_column(String(80))
    authority_level: Mapped[int] = mapped_column(Integer, default=1)
    last_audit_at: Mapped[date] = mapped_column(Date)
    last_decision: Mapped[str] = mapped_column(String(300), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    factors: Mapped[list["TrustFactor"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
        order_by="TrustFactor.id",
        lazy="selectin",
    )
    decisions: Mapped[list["Decision"]] = relationship(back_populates="agent")


class TrustFactor(Base):
    """One weighted signal contributing to an agent's composite trust score."""

    __tablename__ = "trust_factors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agent_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("agents.id", ondelete="CASCADE"), index=True
    )

    key: Mapped[str] = mapped_column(String(40))
    label: Mapped[str] = mapped_column(String(80))
    score: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float)

    agent: Mapped[Agent] = relationship(back_populates="factors")
