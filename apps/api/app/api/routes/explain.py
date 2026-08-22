from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.explain import (
    CounterfactualRead,
    DriverRead,
    ExplanationRead,
    RuleEvidenceRead,
)
from app.services import explanation_service

router = APIRouter(prefix="/explain", tags=["explain"])


@router.get("/decisions/{decision_id}", response_model=ExplanationRead)
async def explain_decision(decision_id: str, db: AsyncSession = Depends(get_db)) -> ExplanationRead:
    """Why this decision came out the way it did, and what would change it.

    Reconstructed from the ledger's pinned evidence — the rule *versions* and
    model that were in force — not from current state. Re-evaluating an old
    decision against today's policies would produce a confident explanation of
    a decision the system never made.
    """
    try:
        result = await explanation_service.explain_decision(db, decision_id)
    except explanation_service.DecisionNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    explanation = result.explanation

    return ExplanationRead(
        decision_id=result.decision_id,
        agent_id=result.agent_id,
        agent_name=result.agent_name,
        action=result.action,
        outcome=explanation.outcome,
        headline=explanation.headline,
        decided_by=explanation.decided_by,
        narrative=explanation.narrative,
        drivers=[
            DriverRead(key=d.key, label=d.label, contribution=d.contribution, value=d.value)
            for d in explanation.drivers
        ],
        drivers_are_current=True,
        rules=[
            RuleEvidenceRead(
                policy_id=r.policy_id,
                policy_name=r.policy_name,
                version=r.version,
                matched=r.matched,
                in_scope=r.in_scope,
                effect=r.effect,
            )
            for r in explanation.rules
        ],
        counterfactuals=[
            CounterfactualRead(
                field=c.field,
                label=c.label,
                current=c.current,
                threshold=c.threshold,
                direction=c.direction,
                changes_to=c.changes_to,
                source=c.source,
                exact=c.exact,
                detail=c.detail,
            )
            for c in explanation.counterfactuals
        ],
        ledger_seq=result.ledger_seq,
        from_pinned_evidence=result.from_pinned_evidence,
    )
