from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.ledger import (
    ChainBreakRead,
    ExecuteDecisionRequest,
    ExecuteDecisionResponse,
    LedgerEntryRead,
    LedgerStatsResponse,
    LedgerVerifyResponse,
)
from app.services import decision_service, ledger_service
from app.services.decision_service import ExecuteRequest

router = APIRouter(prefix="/ledger", tags=["ledger"])

decisions_router = APIRouter(prefix="/decisions", tags=["decisions"])


@decisions_router.post("/execute", response_model=ExecuteDecisionResponse)
async def execute_decision(
    request: ExecuteDecisionRequest, db: AsyncSession = Depends(get_db)
) -> ExecuteDecisionResponse:
    """Run an action through the governance pipeline and commit the outcome.

    Unlike `/simulation/run`, this is the committing path: it writes the
    decision, its policy checks, the simulation that decided it, and an
    append-only ledger entry — all in one transaction.
    """
    try:
        result = await decision_service.execute(
            db,
            ExecuteRequest(
                agent_id=request.agent_id,
                action=request.action,
                amount_usd=request.amount_usd,
                risk_score=request.risk_score,
                hour_utc=request.hour_utc,
                decision_id=request.decision_id,
            ),
        )
    except decision_service.AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except decision_service.DuplicateDecision as exc:
        # 409, not 500: the caller retried a reference that is already on the
        # record, and can fetch the original verdict instead of re-deciding.
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    verdict = result.simulation.verdict
    return ExecuteDecisionResponse(
        decision_id=result.decision.id,
        outcome=result.decision.outcome,
        executed=result.executed,
        agent_name=result.simulation.agent_name,
        trust_score=result.decision.trust_score,
        confidence=verdict.confidence,
        rationale=result.decision.rationale,
        latency_ms=result.decision.latency_ms,
        expected_exposure_usd=verdict.expected_exposure_usd,
        withheld_usd=verdict.withheld_usd,
        ledger_seq=result.ledger_entry.seq,
        ledger_hash=result.ledger_entry.entry_hash,
    )


@router.get("", response_model=list[LedgerEntryRead])
async def list_ledger(
    limit: int = Query(50, ge=1, le=500),
    kind: str | None = None,
    # Aliased so query params stay camelCase like the rest of the contract —
    # the alias generator on ApiModel only covers request and response bodies.
    subject_id: str | None = Query(None, alias="subjectId"),
    db: AsyncSession = Depends(get_db),
) -> list[LedgerEntryRead]:
    entries = await ledger_service.list_entries(db, limit=limit, kind=kind, subject_id=subject_id)
    return [LedgerEntryRead.model_validate(entry) for entry in entries]


@router.get("/verify", response_model=LedgerVerifyResponse)
async def verify_ledger(db: AsyncSession = Depends(get_db)) -> LedgerVerifyResponse:
    """Recompute every hash and check every link.

    Deliberately recomputes rather than trusting a stored flag: a verification
    result that is itself just a database row proves nothing.
    """
    result = await ledger_service.verify(db)
    return LedgerVerifyResponse(
        valid=result.valid,
        entries_checked=result.entries_checked,
        breaks=[
            ChainBreakRead(seq=b.seq, reason=b.reason, expected=b.expected, found=b.found)
            for b in result.breaks
        ],
        head_hash=result.head_hash,
    )


@router.get("/stats", response_model=LedgerStatsResponse)
async def ledger_stats(db: AsyncSession = Depends(get_db)) -> LedgerStatsResponse:
    stats = await ledger_service.stats(db)
    return LedgerStatsResponse(
        entries=stats.entries,
        head_hash=stats.head_hash,
        head_seq=stats.head_seq,
        first_recorded_at=stats.first_recorded_at,
        last_recorded_at=stats.last_recorded_at,
        counts_by_kind=stats.counts_by_kind,
        model_fingerprint=ledger_service.model_fingerprint(),
    )


@router.get("/{seq}", response_model=LedgerEntryRead)
async def get_ledger_entry(seq: int, db: AsyncSession = Depends(get_db)) -> LedgerEntryRead:
    entry = await ledger_service.get_entry(db, seq)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Ledger entry {seq} not found")
    return LedgerEntryRead.model_validate(entry)
