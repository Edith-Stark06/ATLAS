from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireOperator
from app.core.database import get_db
from app.schemas.simulation import (
    PolicyTraceRead,
    PredictedOutcomeRead,
    RebuildResponse,
    SimulateActionRequest,
    SimulateActionResponse,
)
from app.services import simulation_service
from app.services.simulation_service import SimulationRequest

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run", response_model=SimulateActionResponse)
async def run_simulation(
    request: SimulateActionRequest, db: AsyncSession = Depends(get_db)
) -> SimulateActionResponse:
    """Evaluate a proposed action before it executes.

    Runs the whole pre-execution pipeline — trust, policy, and predicted
    outcomes — and returns one recommendation with the evidence behind it.
    Nothing is persisted: this is a what-if, and what-ifs should not appear
    in the audit trail alongside decisions that actually happened.
    """
    try:
        result = await simulation_service.run(
            db,
            SimulationRequest(
                agent_id=request.agent_id,
                action=request.action,
                amount_usd=request.amount_usd,
                risk_score=request.risk_score,
                trust_score=request.trust_score,
                hour_utc=request.hour_utc,
                policy_pass_rate=request.policy_pass_rate,
            ),
        )
    except simulation_service.AgentNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    verdict = result.verdict

    return SimulateActionResponse(
        recommendation=verdict.recommendation,
        confidence=verdict.confidence,
        outcomes=[
            PredictedOutcomeRead(
                outcome=o.outcome,
                label=o.label,
                probability=o.probability,
                financial_impact_usd=o.financial_impact_usd,
                risk_score=o.risk_score,
                compliant=o.compliant,
                recommended=o.recommended,
            )
            for o in verdict.outcomes
        ],
        expected_exposure_usd=verdict.expected_exposure_usd,
        withheld_usd=verdict.withheld_usd,
        unconstrained_exposure_usd=verdict.unconstrained_exposure_usd,
        adverse_probability=verdict.adverse_probability,
        policy_forced=verdict.policy_forced,
        policy_effect=result.policy_effect,
        policy_trace=[
            PolicyTraceRead(
                policy_id=detail.policy_id,
                policy_name=detail.policy_name,
                version=detail.version,
                matched=detail.evaluation.matched,
                in_scope=detail.evaluation.in_scope,
                effect=detail.evaluation.effect,
            )
            for detail in result.policy_evaluations
        ],
        agent_name=result.agent_name,
        trust_score=result.trust_score,
        model_backed=result.model_backed,
        duration_ms=result.duration_ms,
        explanation=verdict.explanation,
    )


@router.post(
    "/rebuild",
    response_model=RebuildResponse,
    # Deletes and regenerates every stored run.
    dependencies=[RequireOperator],
)
async def rebuild(db: AsyncSession = Depends(get_db)) -> RebuildResponse:
    """Regenerate every stored simulation from the current engine.

    The seeded runs shipped with hand-written outcome percentages; this
    replaces them with model-backed predictions, so the console shows
    something the system actually computed.
    """
    rebuilt = await simulation_service.rebuild_for_decisions(db)
    return RebuildResponse(rebuilt=rebuilt)
