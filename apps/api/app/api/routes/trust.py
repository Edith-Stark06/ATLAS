import math

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireOperator
from app.core.database import get_db
from app.ml import models as ml_models
from app.models import Agent
from app.schemas.governance import TrustFactorRead
from app.schemas.trust import (
    DriftRead,
    MLAnomalyRead,
    ModelInfoRead,
    PredictedOutcome,
    RecomputeResponse,
    RecomputeResult,
    SimulationPredictRequest,
    SimulationPredictResponse,
    TrustBandCount,
    TrustEvaluationRead,
    TrustOverviewRead,
    TrustSnapshotRead,
)
from app.services import trust_engine, trust_service

router = APIRouter(prefix="/trust", tags=["trust"])

#: Most agents returned in the overview watchlist.
WATCHLIST_LIMIT = 25

BANDS = [
    ("trusted", "Trusted", trust_engine.TRUSTED_MIN, 101),
    ("healthy", "Healthy", trust_engine.HEALTHY_MIN, trust_engine.TRUSTED_MIN),
    ("watch", "Watch", trust_engine.REVIEW_BELOW, trust_engine.HEALTHY_MIN),
    ("restricted", "Restricted", 0, trust_engine.REVIEW_BELOW),
]


async def _read_evaluation(
    db: AsyncSession, agent_id: str, *, include_ml_anomaly: bool = False
) -> TrustEvaluationRead | None:
    """Build one agent's evaluation response.

    `include_ml_anomaly` is opt-in because fitting the per-agent anomaly
    detector costs ~340ms and only the detail view renders the result.
    """
    loaded = await trust_service.evaluate_agent(db, agent_id, include_ml_anomaly=include_ml_anomaly)
    if loaded is None:
        return None

    agent, evaluation, snapshots, ml_anomaly = loaded
    return TrustEvaluationRead(
        agent_id=agent.id,
        agent_name=agent.name,
        score=evaluation.score,
        base_score=evaluation.base_score,
        anomaly_penalty=evaluation.anomaly_penalty,
        lifecycle=evaluation.lifecycle,
        factors=[TrustFactorRead.model_validate(f) for f in evaluation.factors],
        drift=DriftRead(
            detected=evaluation.drift.detected,
            delta=evaluation.drift.delta,
            baseline=evaluation.drift.baseline,
            samples=evaluation.drift.samples,
        ),
        forecast=trust_engine.forecast(snapshots),
        explanation=evaluation.explanation,
        history=[TrustSnapshotRead.model_validate(s) for s in snapshots],
        score_source=evaluation.score_source,
        ml_attribution=evaluation.ml_attribution,
        ml_anomaly=(
            MLAnomalyRead(detected=ml_anomaly.detected, score=ml_anomaly.score)
            if ml_anomaly is not None
            else None
        ),
    )


@router.get("/overview", response_model=TrustOverviewRead)
async def trust_overview(db: AsyncSession = Depends(get_db)) -> TrustOverviewRead:
    agent_ids = list((await db.execute(select(Agent.id))).scalars().all())

    evaluations = []
    for agent_id in agent_ids:
        evaluation = await _read_evaluation(db, agent_id)
        if evaluation is not None:
            evaluations.append(evaluation)

    if not evaluations:
        return TrustOverviewRead(
            average_score=0, agents_evaluated=0, drifting=0, bands=[], watchlist=[]
        )

    bands = [
        TrustBandCount(
            band=key,
            label=label,
            count=sum(1 for e in evaluations if low <= e.score < high),
        )
        for key, label, low, high in BANDS
    ]

    # Worst drift first; agents that are not drifting sort last. Capped so a
    # large estate does not return everything — the UI states what it shows.
    watchlist = sorted(evaluations, key=lambda e: e.drift.delta)[:WATCHLIST_LIMIT]

    return TrustOverviewRead(
        average_score=round(sum(e.score for e in evaluations) / len(evaluations)),
        agents_evaluated=len(evaluations),
        drifting=sum(1 for e in evaluations if e.drift.detected),
        bands=bands,
        watchlist=watchlist,
    )


@router.get("/agents/{agent_id}", response_model=TrustEvaluationRead)
async def agent_trust(agent_id: str, db: AsyncSession = Depends(get_db)) -> TrustEvaluationRead:
    # The one caller that renders the ML anomaly, so the one that pays for it.
    evaluation = await _read_evaluation(db, agent_id, include_ml_anomaly=True)
    if evaluation is None:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_id}' not found")
    return evaluation


@router.get("/model-info", response_model=ModelInfoRead)
async def model_info() -> ModelInfoRead:
    """Provenance and evaluation results for the trained models — the
    baseline-vs-learned comparison, not asserted, read back from what
    `python -m app.ml.train` actually measured."""
    metrics = ml_models.load_metrics()
    if metrics is None:
        return ModelInfoRead(available=False)
    return ModelInfoRead(available=True, trained_at=metrics.get("trained_at"), metrics=metrics)


@router.post("/simulate", response_model=SimulationPredictResponse)
async def simulate(request: SimulationPredictRequest) -> SimulationPredictResponse:
    """Score a hypothetical decision with the trained outcome classifier.

    No persistence and no agent lookup — this is a what-if tool, distinct
    from the historical SimulationRun rows attached to real decisions.
    """
    model = ml_models.load_simulation_model()
    if model is None:
        raise HTTPException(
            status_code=503,
            detail="Simulation model not trained — run `python -m app.ml.train`.",
        )

    features = {
        "risk_score": request.risk_score,
        "log_amount": math.log1p(request.amount_usd),
        "hour": request.hour,
        "policy_pass_rate": request.policy_pass_rate,
        "trust_proxy": request.trust_score,
        "authority_level": request.authority_level,
    }
    predictions = model.predict_outcomes(features)
    best = max(predictions, key=lambda p: p["probability"])

    return SimulationPredictResponse(
        outcomes=[PredictedOutcome(**p) for p in predictions],
        recommendation=best["outcome"],
    )


@router.post(
    "/recompute",
    response_model=RecomputeResponse,
    # Writes snapshots and moves agents between lifecycle states.
    dependencies=[RequireOperator],
)
async def recompute(db: AsyncSession = Depends(get_db)) -> RecomputeResponse:
    """Re-evaluate every agent and record a new snapshot for each."""
    previous = {
        agent_id: score
        for agent_id, score in (await db.execute(select(Agent.id, Agent.trust_score))).all()
    }

    outcomes = await trust_service.recompute_all(db)

    return RecomputeResponse(
        evaluated=len(outcomes),
        results=[
            RecomputeResult(
                agent_id=agent.id,
                agent_name=agent.name,
                previous_score=previous.get(agent.id, agent.trust_score),
                score=evaluation.score,
                lifecycle=evaluation.lifecycle,
                drift_detected=evaluation.drift.detected,
            )
            for agent, evaluation in outcomes
        ],
    )
