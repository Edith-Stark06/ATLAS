"""Database side of the governance ledger.

The only write path is `append`. There is deliberately no update or delete
function: the integrity guarantee in `app/services/ledger.py` is worth
exactly as much as the discipline around it, and an `edit_entry` helper
would quietly cost more than the chain buys.
"""

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml import models as ml_models
from app.models import LedgerEntry
from app.services import ledger


@dataclass(frozen=True)
class LedgerStats:
    entries: int
    head_hash: str | None
    head_seq: int | None
    first_recorded_at: datetime | None
    last_recorded_at: datetime | None
    counts_by_kind: dict[str, int]


@lru_cache(maxsize=1)
def model_fingerprint() -> str | None:
    """SHA-256 over the trained artifacts on disk.

    `metrics.json` carries a `trained_at` timestamp, but a timestamp is a
    claim about a model, not the model itself. Hashing the bytes pins the
    exact estimator that produced a verdict, so "which model decided this?"
    has an answer that survives a retrain.

    Cached: the files do not change while the process runs, and re-reading
    several megabytes per decision would put disk I/O in the hot path.
    """
    artifacts = sorted(ml_models.artifacts_dir().glob("*.joblib"))
    if not artifacts:
        return None

    digest = hashlib.sha256()
    for path in artifacts:
        # The filename is hashed too, so swapping two artifacts is detectable.
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


async def append(
    db: AsyncSession,
    *,
    kind: str,
    subject_id: str,
    payload: dict[str, Any],
    recorded_at: datetime | None = None,
) -> LedgerEntry:
    """Append one entry, linked to the current head.

    Not concurrency-safe on its own: two simultaneous appends can read the
    same head and produce a forked chain. The caller holds a transaction, and
    the unique constraint on `entry_hash` turns an exact duplicate into an
    error rather than a silent second write — but a busy multi-writer
    deployment needs a serialisable transaction or an advisory lock on the
    head. Called out here rather than papered over, because a hash chain that
    forks under load is worse than no chain at all.
    """
    head = (
        await db.execute(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    ).scalar_one_or_none()

    seq = (head.seq + 1) if head else 1
    prev_hash = head.entry_hash if head else ledger.GENESIS_HASH
    moment = recorded_at or datetime.now(UTC)

    entry_hash = ledger.compute_hash(
        seq=seq,
        prev_hash=prev_hash,
        kind=kind,
        subject_id=subject_id,
        recorded_at=moment,
        payload=payload,
    )

    entry = LedgerEntry(
        seq=seq,
        entry_hash=entry_hash,
        prev_hash=prev_hash,
        kind=kind,
        subject_id=subject_id,
        payload=payload,
        recorded_at=moment,
    )
    db.add(entry)
    await db.flush()
    return entry


async def load_chain(db: AsyncSession) -> list[LedgerEntry]:
    """Every entry in chain order. Verification needs all of them — a
    partial window cannot prove the part it cannot see."""
    result = await db.execute(select(LedgerEntry).order_by(LedgerEntry.seq))
    return list(result.scalars().all())


async def verify(db: AsyncSession) -> ledger.ChainVerification:
    return ledger.verify_chain(await load_chain(db))


async def list_entries(
    db: AsyncSession,
    *,
    limit: int = 50,
    kind: str | None = None,
    subject_id: str | None = None,
) -> list[LedgerEntry]:
    """Newest first — the console reads the ledger as a timeline."""
    query = select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(limit)
    if kind is not None:
        query = query.where(LedgerEntry.kind == kind)
    if subject_id is not None:
        query = query.where(LedgerEntry.subject_id == subject_id)
    return list((await db.execute(query)).scalars().all())


async def get_entry(db: AsyncSession, seq: int) -> LedgerEntry | None:
    return await db.get(LedgerEntry, seq)


async def stats(db: AsyncSession) -> LedgerStats:
    head = (
        await db.execute(select(LedgerEntry).order_by(LedgerEntry.seq.desc()).limit(1))
    ).scalar_one_or_none()

    totals = (
        await db.execute(
            select(
                func.count(LedgerEntry.seq),
                func.min(LedgerEntry.recorded_at),
                func.max(LedgerEntry.recorded_at),
            )
        )
    ).one()

    by_kind = (
        await db.execute(
            select(LedgerEntry.kind, func.count(LedgerEntry.seq)).group_by(LedgerEntry.kind)
        )
    ).all()

    return LedgerStats(
        entries=totals[0] or 0,
        head_hash=head.entry_hash if head else None,
        head_seq=head.seq if head else None,
        first_recorded_at=totals[1],
        last_recorded_at=totals[2],
        counts_by_kind={kind: count for kind, count in by_kind},
    )
