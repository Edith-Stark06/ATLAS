from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import DecisionOutcome
from app.schemas.base import ApiModel


class ExecuteDecisionRequest(ApiModel):
    """An action an agent proposes to take, for real."""

    agent_id: str
    action: str = Field(max_length=300)
    amount_usd: float | None = None
    risk_score: int = Field(default=20, ge=0, le=100)
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    #: Reference from the originating enterprise system. Generated when absent
    #: so callers without their own id scheme still get a usable record.
    decision_id: str | None = Field(default=None, max_length=64)


class ExecuteDecisionResponse(ApiModel):
    decision_id: str
    outcome: DecisionOutcome
    #: True only when the action is cleared to run. Callers should branch on
    #: this rather than string-matching the outcome.
    executed: bool
    agent_name: str
    trust_score: int
    confidence: float
    rationale: str
    latency_ms: int

    expected_exposure_usd: float
    withheld_usd: float

    #: Position and hash of the audit record written for this decision, so a
    #: caller can cite it without a second request.
    ledger_seq: int
    ledger_hash: str


class LedgerEntryRead(ApiModel):
    seq: int
    entry_hash: str
    prev_hash: str
    kind: str
    subject_id: str
    payload: dict[str, Any]
    recorded_at: datetime


class ChainBreakRead(ApiModel):
    seq: int
    reason: str
    expected: str
    found: str


class LedgerVerifyResponse(ApiModel):
    valid: bool
    entries_checked: int
    breaks: list[ChainBreakRead]
    #: Hash of the newest entry. Publishing this externally is what would turn
    #: tamper-evidence into tamper-proofing; the API only reports it.
    head_hash: str | None
    #: False when `sinceSeq` was supplied — entries strictly before that
    #: checkpoint were not re-examined by this call. A caller must not read
    #: `valid: true` here as "the whole chain is intact" unless this is true.
    complete: bool = True


class LedgerStatsResponse(ApiModel):
    entries: int
    head_hash: str | None
    head_seq: int | None
    first_recorded_at: datetime | None
    last_recorded_at: datetime | None
    counts_by_kind: dict[str, int]
    #: SHA-256 of the trained artifacts currently on disk. A decision whose
    #: pinned fingerprint differs was made by a different model.
    model_fingerprint: str | None
