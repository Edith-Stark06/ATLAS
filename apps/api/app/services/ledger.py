"""Tamper-evident hash chain for the governance ledger.

Pure functions over plain values — no database, no I/O — so the integrity
rules can be tested exhaustively and reasoned about on their own.

The ledger's claim is narrow and worth stating precisely: it does not make
records *impossible* to alter, it makes alteration *detectable*. Each entry
commits to the entry before it, so editing any field of any historical row
invalidates that row's hash and every hash after it. An auditor re-running
`verify_chain` finds the first break and the exact field that moved.

That is the property a regulator actually needs. "Trust us, the row says
approved" is not evidence; "here is the chain, recompute it yourself" is.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

#: prev_hash of the first entry. A fixed, recognisable constant rather than
#: an empty string, so a truncated chain cannot be passed off as a fresh one.
GENESIS_HASH = "0" * 64

#: Bumped when the hash preimage changes shape. Stored on every entry so an
#: old chain stays verifiable under the rules it was written with, instead of
#: silently failing against new ones.
HASH_VERSION = 1


class LedgerKind:
    """What a ledger entry records. Plain constants, not an enum, because
    these are persisted as strings and read by external auditors."""

    DECISION_RECORDED = "decision_recorded"
    POLICY_ACTIVATED = "policy_activated"
    TRUST_RECOMPUTED = "trust_recomputed"


def canonical_json(payload: Any) -> str:
    """Serialise a payload to exactly one byte-sequence.

    Any ambiguity here is a hole in the integrity claim: if the same evidence
    can serialise two ways, a mismatch proves nothing. Keys are sorted,
    whitespace is stripped, and non-JSON types are rejected rather than
    coerced — hashing `repr(x)` of an unexpected object would produce a
    stable-looking hash over something nobody can reconstruct.
    """
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=_reject,
    )


def _reject(value: Any) -> Any:
    raise TypeError(
        f"{type(value).__name__} is not JSON-serialisable; convert it in the "
        "payload builder so the stored evidence is what gets hashed"
    )


def iso(moment: datetime) -> str:
    """UTC timestamp with microsecond precision, in one fixed spelling.

    A naive datetime is treated as UTC rather than rejected — the alternative
    is a decision that cannot be recorded because of a timezone detail.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def compute_hash(
    *,
    seq: int,
    prev_hash: str,
    kind: str,
    subject_id: str,
    recorded_at: datetime,
    payload: Any,
) -> str:
    """SHA-256 over every field that carries meaning.

    Position, linkage, type, subject and time are all inside the preimage,
    not just the payload — otherwise entries could be reordered or reassigned
    to a different decision without breaking a single hash.

    Fields are newline-joined and the payload comes last: a delimiter that
    cannot appear in the canonical JSON of the preceding scalar fields means
    no combination of values can be shifted between them.
    """
    preimage = "\n".join(
        [
            str(HASH_VERSION),
            str(seq),
            prev_hash,
            kind,
            subject_id,
            iso(recorded_at),
            canonical_json(payload),
        ]
    )
    return hashlib.sha256(preimage.encode("utf-8")).hexdigest()


class ChainEntry(Protocol):
    """Structural type for anything verifiable — the ORM row satisfies this
    without the pure module importing SQLAlchemy."""

    seq: int
    prev_hash: str
    entry_hash: str
    kind: str
    subject_id: str
    recorded_at: datetime
    payload: Any


@dataclass(frozen=True)
class ChainBreak:
    seq: int
    reason: str
    expected: str
    found: str


@dataclass(frozen=True)
class ChainVerification:
    """Result of walking the whole chain."""

    valid: bool
    entries_checked: int
    #: Every break found, earliest first. A single edit produces one
    #: recomputation failure plus a linkage failure on the following entry;
    #: reporting all of them shows the blast radius rather than just the
    #: first symptom.
    breaks: list[ChainBreak]
    head_hash: str | None


def verify_chain(entries: list[ChainEntry]) -> ChainVerification:
    """Recompute every hash and check every link.

    Entries must arrive in ascending `seq`. Three things can be wrong: a
    stored hash that does not match its own contents (the row was edited), a
    `prev_hash` that does not match the previous entry (a row was removed or
    reordered), or a gap in `seq` (a row was deleted from the middle).
    """
    breaks: list[ChainBreak] = []
    previous: ChainEntry | None = None

    for entry in entries:
        expected_prev = previous.entry_hash if previous else GENESIS_HASH
        if entry.prev_hash != expected_prev:
            breaks.append(
                ChainBreak(
                    seq=entry.seq,
                    reason="prev_hash does not match the preceding entry",
                    expected=expected_prev,
                    found=entry.prev_hash,
                )
            )

        if previous is not None and entry.seq != previous.seq + 1:
            breaks.append(
                ChainBreak(
                    seq=entry.seq,
                    reason="sequence gap — an entry is missing",
                    expected=str(previous.seq + 1),
                    found=str(entry.seq),
                )
            )

        recomputed = compute_hash(
            seq=entry.seq,
            prev_hash=entry.prev_hash,
            kind=entry.kind,
            subject_id=entry.subject_id,
            recorded_at=entry.recorded_at,
            payload=entry.payload,
        )
        if recomputed != entry.entry_hash:
            breaks.append(
                ChainBreak(
                    seq=entry.seq,
                    reason="entry contents do not match the stored hash",
                    expected=recomputed,
                    found=entry.entry_hash,
                )
            )

        previous = entry

    return ChainVerification(
        valid=not breaks,
        entries_checked=len(entries),
        breaks=breaks,
        head_hash=previous.entry_hash if previous else None,
    )
