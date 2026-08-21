"""Unit tests for the governance ledger's hash chain.

Pure functions over plain values — no database. These are the tests the
integrity claim rests on: if tampering is not detected here, nothing built on
top of it means anything.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.services.ledger import (
    GENESIS_HASH,
    LedgerKind,
    canonical_json,
    compute_hash,
    iso,
    verify_chain,
)

MOMENT = datetime(2026, 8, 22, 9, 30, 15, 123456, tzinfo=UTC)


@dataclass
class FakeEntry:
    """Stands in for the ORM row — verify_chain takes a structural type."""

    seq: int
    prev_hash: str
    entry_hash: str
    kind: str
    subject_id: str
    recorded_at: datetime
    payload: Any


def build_chain(count: int = 3) -> list[FakeEntry]:
    entries: list[FakeEntry] = []
    prev = GENESIS_HASH
    for i in range(1, count + 1):
        moment = MOMENT + timedelta(seconds=i)
        payload = {"decision": {"id": f"TRX-{i:04d}", "outcome": "approved"}}
        entry_hash = compute_hash(
            seq=i,
            prev_hash=prev,
            kind=LedgerKind.DECISION_RECORDED,
            subject_id=f"TRX-{i:04d}",
            recorded_at=moment,
            payload=payload,
        )
        entries.append(
            FakeEntry(
                seq=i,
                prev_hash=prev,
                entry_hash=entry_hash,
                kind=LedgerKind.DECISION_RECORDED,
                subject_id=f"TRX-{i:04d}",
                recorded_at=moment,
                payload=payload,
            )
        )
        prev = entry_hash
    return entries


# --- canonical serialisation -------------------------------------------------


def test_key_order_does_not_change_the_serialisation():
    """Two dicts with the same content must hash identically — otherwise a
    mismatch proves nothing about tampering."""
    assert canonical_json({"b": 1, "a": 2}) == canonical_json({"a": 2, "b": 1})


def test_nested_key_order_does_not_change_the_serialisation():
    left = {"outer": {"z": 1, "a": {"y": 2, "b": 3}}}
    right = {"outer": {"a": {"b": 3, "y": 2}, "z": 1}}
    assert canonical_json(left) == canonical_json(right)


def test_serialisation_has_no_incidental_whitespace():
    assert canonical_json({"a": 1, "b": [1, 2]}) == '{"a":1,"b":[1,2]}'


def test_non_json_types_are_rejected_rather_than_coerced():
    """Hashing repr() of an unexpected object would give a stable-looking
    hash over something nobody can reconstruct."""
    with pytest.raises(TypeError):
        canonical_json({"amount": object()})


def test_nan_is_rejected():
    """NaN is not valid JSON and never equals itself — a payload containing
    one could never be re-verified."""
    with pytest.raises(ValueError):
        canonical_json({"score": float("nan")})


def test_unicode_survives_verbatim():
    """An action described in non-ASCII text must hash as itself, not as
    escape sequences that a different serialiser would spell differently."""
    assert "café" in canonical_json({"action": "café"})


# --- timestamps --------------------------------------------------------------


def test_timestamps_are_normalised_to_utc():
    """The same instant written in two timezones must produce one string."""
    from datetime import timezone

    tokyo = MOMENT.astimezone(timezone(timedelta(hours=9)))
    assert iso(tokyo) == iso(MOMENT)


def test_naive_timestamps_are_treated_as_utc():
    assert iso(MOMENT.replace(tzinfo=None)) == iso(MOMENT)


def test_microseconds_are_preserved():
    """Truncating to seconds would let two decisions in the same second
    become indistinguishable in the hash preimage."""
    assert iso(MOMENT).endswith(".123456Z")


# --- hashing -----------------------------------------------------------------


def test_hashing_is_deterministic():
    args = dict(
        seq=1,
        prev_hash=GENESIS_HASH,
        kind=LedgerKind.DECISION_RECORDED,
        subject_id="TRX-0001",
        recorded_at=MOMENT,
        payload={"a": 1},
    )
    assert compute_hash(**args) == compute_hash(**args)


@pytest.mark.parametrize(
    "field,value",
    [
        ("seq", 2),
        ("prev_hash", "f" * 64),
        ("kind", LedgerKind.POLICY_ACTIVATED),
        ("subject_id", "TRX-9999"),
        ("recorded_at", MOMENT + timedelta(microseconds=1)),
        ("payload", {"a": 2}),
    ],
)
def test_every_field_is_covered_by_the_hash(field, value):
    """Position, linkage, type, subject and time are all inside the preimage.
    If any were left out, entries could be reordered or reassigned to a
    different decision without breaking a single hash."""
    args: dict[str, Any] = dict(
        seq=1,
        prev_hash=GENESIS_HASH,
        kind=LedgerKind.DECISION_RECORDED,
        subject_id="TRX-0001",
        recorded_at=MOMENT,
        payload={"a": 1},
    )
    baseline = compute_hash(**args)
    assert compute_hash(**{**args, field: value}) != baseline


def test_fields_cannot_be_shifted_across_the_delimiter():
    """Concatenating fields without a safe delimiter would let one value
    borrow characters from the next and hash the same."""
    left = compute_hash(
        seq=1,
        prev_hash=GENESIS_HASH,
        kind="decision",
        subject_id="recorded",
        recorded_at=MOMENT,
        payload={},
    )
    right = compute_hash(
        seq=1,
        prev_hash=GENESIS_HASH,
        kind="decision_recorded",
        subject_id="",
        recorded_at=MOMENT,
        payload={},
    )
    assert left != right


# --- chain verification ------------------------------------------------------


def test_an_untouched_chain_verifies():
    result = verify_chain(build_chain())

    assert result.valid is True
    assert result.entries_checked == 3
    assert result.breaks == []


def test_an_empty_chain_is_valid():
    """No records is not the same as broken records."""
    result = verify_chain([])

    assert result.valid is True
    assert result.head_hash is None


def test_the_head_hash_is_the_newest_entry():
    chain = build_chain()
    assert verify_chain(chain).head_hash == chain[-1].entry_hash


def test_the_first_entry_must_link_to_genesis():
    """A truncated chain must not pass as a fresh one."""
    chain = build_chain()
    chain[0].prev_hash = "a" * 64

    result = verify_chain(chain)
    assert result.valid is False
    assert any("prev_hash" in b.reason for b in result.breaks)


def test_editing_a_payload_is_detected():
    """The headline property: changing a recorded outcome after the fact
    invalidates that entry's hash."""
    chain = build_chain()
    chain[1].payload = {"decision": {"id": "TRX-0002", "outcome": "blocked"}}

    result = verify_chain(chain)
    assert result.valid is False
    assert any(b.seq == 2 and "stored hash" in b.reason for b in result.breaks)


def test_editing_an_entry_also_breaks_every_entry_after_it():
    """Re-hashing the edited row alone is not enough to hide the edit — the
    next entry's prev_hash still points at the original."""
    chain = build_chain()
    tampered = replace(chain[1], payload={"decision": {"outcome": "approved"}})
    tampered.entry_hash = compute_hash(
        seq=tampered.seq,
        prev_hash=tampered.prev_hash,
        kind=tampered.kind,
        subject_id=tampered.subject_id,
        recorded_at=tampered.recorded_at,
        payload=tampered.payload,
    )
    chain[1] = tampered

    result = verify_chain(chain)
    assert result.valid is False
    # Entry 2 now hashes correctly, so the break surfaces at entry 3.
    assert any(b.seq == 3 for b in result.breaks)


def test_deleting_an_entry_is_detected():
    chain = build_chain(4)
    del chain[1]

    result = verify_chain(chain)
    assert result.valid is False
    reasons = " ".join(b.reason for b in result.breaks)
    assert "sequence gap" in reasons or "prev_hash" in reasons


def test_reordering_entries_is_detected():
    chain = build_chain(3)
    chain[1], chain[2] = chain[2], chain[1]

    assert verify_chain(chain).valid is False


def test_a_break_reports_what_was_expected_and_what_was_found():
    """An auditor needs to see the discrepancy, not just a boolean."""
    chain = build_chain()
    chain[1].payload = {"tampered": True}

    break_ = next(b for b in verify_chain(chain).breaks if b.seq == 2)
    assert break_.expected != break_.found
    assert len(break_.expected) == 64
