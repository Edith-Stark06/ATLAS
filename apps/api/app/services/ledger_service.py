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
    partial window cannot prove the part it cannot see (see verify_chain's
    own docstring on why a fast, partial check is a different, weaker
    guarantee, not a faster version of this one).

    Fetched via a server-side cursor (`stream_scalars`, `yield_per`) rather
    than one query that buffers the whole resultset in the driver at once —
    this bounds *database-side* memory. The returned list is still the full
    ordered chain, and is still O(n) in Python-side memory: that part is not
    optimised away, because nothing here can prove the part it doesn't see,
    which is exactly the constraint that made this "unbounded" in the first
    place. What changes is where the resultset gets buffered, not how much
    of the chain a full verification has to look at.
    """
    query = select(LedgerEntry).order_by(LedgerEntry.seq).execution_options(yield_per=1000)
    result = await db.stream_scalars(query)
    return [entry async for entry in result]


async def verify(db: AsyncSession) -> ledger.ChainVerification:
    return ledger.verify_chain(await load_chain(db))


async def verify_since(db: AsyncSession, since_seq: int) -> ledger.ChainVerification | None:
    """Fast path: verify only what's new since `since_seq`, plus that the
    anchor entry at `since_seq` itself still matches its recorded hash.

    Deliberately weaker than `verify()`, and documented as such rather than
    silently: entries strictly *before* the anchor are never re-examined by
    this call. A tamper to some entry in the middle of an already-checked
    region is invisible here — only a full walk (`verify()`) can catch that.
    This exists for cheap, frequent polling ("has anything changed since I
    last looked"), not as a replacement for periodic full verification.

    Returns None if `since_seq` names no real entry, so the caller can 404
    rather than silently reporting an empty/vacuous result as a valid chain.
    """
    anchor = await db.get(LedgerEntry, since_seq)
    if anchor is None:
        return None

    anchor_recomputed = ledger.compute_hash(
        seq=anchor.seq,
        prev_hash=anchor.prev_hash,
        kind=anchor.kind,
        subject_id=anchor.subject_id,
        recorded_at=anchor.recorded_at,
        payload=anchor.payload,
    )
    if anchor_recomputed != anchor.entry_hash:
        # The checkpoint itself was altered — nothing past it can be trusted
        # either, since every later hash is built on this one.
        return ledger.ChainVerification(
            valid=False,
            entries_checked=0,
            breaks=[
                ledger.ChainBreak(
                    seq=anchor.seq,
                    reason="anchor entry's contents do not match its stored hash",
                    expected=anchor_recomputed,
                    found=anchor.entry_hash,
                )
            ],
            head_hash=anchor.entry_hash,
        )

    new_entries = list(
        (
            await db.execute(
                select(LedgerEntry).where(LedgerEntry.seq > since_seq).order_by(LedgerEntry.seq)
            )
        )
        .scalars()
        .all()
    )
    return ledger.verify_chain(new_entries, start_from=anchor)


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
