from datetime import datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LedgerEntry(Base):
    """One append-only record in the governance ledger.

    Nothing in the application ever updates or deletes a row here; the only
    write path is `ledger_service.append`. The hash chain is what makes that
    discipline checkable rather than merely claimed — see
    `app/services/ledger.py`.

    Note this is tamper-*evident*, not tamper-*proof*: anyone with direct
    database access can still edit a row. What they cannot do is make the
    edit verify. Tamper-proofing needs the chain head anchored somewhere the
    same operator does not control, which is a deployment concern, not a
    schema one.
    """

    __tablename__ = "ledger_entries"

    #: Monotonic position in the chain. The hash commits to it, so entries
    #: cannot be reordered or renumbered without detection.
    seq: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)

    #: SHA-256 of this entry, unique so a replayed entry cannot be appended twice.
    entry_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    #: The preceding entry's hash; GENESIS_HASH for the first.
    prev_hash: Mapped[str] = mapped_column(String(64), index=True)

    #: See ledger.LedgerKind. Stored as a plain string rather than a Postgres
    #: enum: adding a new record type must never require a migration that
    #: rewrites a table auditors depend on.
    kind: Mapped[str] = mapped_column(String(40), index=True)

    #: The decision, policy or agent this entry is about. Deliberately not a
    #: foreign key — an audit record must survive the deletion of the thing
    #: it describes, and an FK would either block that or cascade the history
    #: away with it.
    subject_id: Mapped[str] = mapped_column(String(64), index=True)

    #: The pinned evidence: outcome, trust score, policy versions in force,
    #: and model fingerprint at the moment of the decision. Hashed verbatim,
    #: so this is what an auditor recomputes against.
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        # The ledger is read as a filtered timeline far more often than by id.
        Index("ix_ledger_entries_kind_seq", "kind", "seq"),
    )
