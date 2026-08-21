from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Severity

if TYPE_CHECKING:
    pass


class Policy(Base):
    """A governance rule evaluated by the Policy Brain.

    This row is the policy's stable identity and current pointer; the rule
    logic itself lives in immutable `PolicyVersion` rows. Editing a policy
    creates a new version rather than mutating the old one, so a decision
    recorded months ago can still be explained against the exact rule text
    that produced it.
    """

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    #: Denormalised label of the active version, e.g. "v2.4.1". The
    #: authoritative pointer is active_version_id.
    version: Mapped[str] = mapped_column(String(40))
    scope: Mapped[str] = mapped_column(String(160))

    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity", values_callable=lambda e: [m.value for m in e])
    )

    evaluations_24h: Mapped[int] = mapped_column(Integer, default=0)
    violations_24h: Mapped[int] = mapped_column(Integer, default=0)

    #: Nullable so a policy can exist before its first version is written,
    #: and so deleting a version never orphans the policy row.
    active_version_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("policy_versions.id", ondelete="SET NULL"), nullable=True
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    active_version: Mapped["PolicyVersion | None"] = relationship(
        foreign_keys=[active_version_id], lazy="selectin", post_update=True
    )
    versions: Mapped[list["PolicyVersion"]] = relationship(
        back_populates="policy",
        foreign_keys="PolicyVersion.policy_id",
        cascade="all, delete-orphan",
        order_by="PolicyVersion.created_at.desc()",
    )


class PolicyVersion(Base):
    """One immutable revision of a policy's rule.

    Never updated after insert. "Editing" a policy appends a new version and
    repoints Policy.active_version_id — which is what makes the policy
    ledger genuinely auditable rather than merely labelled as such.
    """

    __tablename__ = "policy_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    policy_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("policies.id", ondelete="CASCADE"), index=True
    )

    version: Mapped[str] = mapped_column(String(40))

    #: The rule as structured data — see app/services/policy_engine.py.
    #: JSONB because the condition list is variable-length and is always
    #: read as a whole; splitting conditions into their own table would add
    #: joins without enabling any query we actually make.
    rule: Mapped[dict[str, Any]] = mapped_column(JSONB)

    #: Free-text note explaining why this revision exists.
    note: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[str] = mapped_column(String(120), default="system")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    policy: Mapped[Policy] = relationship(back_populates="versions", foreign_keys=[policy_id])
