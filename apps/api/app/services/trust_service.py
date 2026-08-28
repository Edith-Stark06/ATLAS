"""Database-facing orchestration around the Trust Engine."""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ml import models as ml_models
from app.models import Agent, Decision, TrustSnapshot
from app.services import trust_engine
from app.services.trust_engine import TrustEvaluation

SNAPSHOT_HISTORY_LIMIT = 40


@dataclass(frozen=True)
class MLAnomalyResult:
    detected: bool
    #: Isolation Forest decision_function output for the current point —
    #: more negative is more anomalous. Not on a fixed scale like the
    #: heuristic drift delta; exposed for ordering/debugging, not comparison.
    score: float


def _factor_dict(rows) -> dict[str, float]:
    """Normalises both ORM TrustFactor rows and the JSONB dicts stored on a
    TrustSnapshot into one {key: score} shape."""
    result = {}
    for row in rows:
        key = row.key if hasattr(row, "key") else row["key"]
        score = row.score if hasattr(row, "score") else row["score"]
        result[key] = score
    return result


async def _load_agent(db: AsyncSession, agent_id: str) -> Agent | None:
    result = await db.execute(
        select(Agent).options(selectinload(Agent.factors)).where(Agent.id == agent_id)
    )
    return result.scalar_one_or_none()


async def _load_decisions(db: AsyncSession, agent_id: str) -> list[Decision]:
    result = await db.execute(
        select(Decision).where(Decision.agent_id == agent_id).order_by(Decision.decided_at)
    )
    return list(result.unique().scalars().all())


async def load_snapshots(
    db: AsyncSession, agent_id: str, *, limit: int = SNAPSHOT_HISTORY_LIMIT
) -> list[TrustSnapshot]:
    """Most recent snapshots, returned oldest → newest for charting."""
    result = await db.execute(
        select(TrustSnapshot)
        .where(TrustSnapshot.agent_id == agent_id)
        .order_by(TrustSnapshot.captured_at.desc())
        .limit(limit)
    )
    return list(reversed(list(result.scalars().all())))


async def evaluate_agent(
    db: AsyncSession,
    agent_id: str,
    *,
    now: datetime | None = None,
    include_ml_anomaly: bool = False,
) -> tuple[Agent, TrustEvaluation, list[TrustSnapshot], MLAnomalyResult | None] | None:
    """Evaluate an agent without persisting anything.

    Uses the trained trust model when `python -m app.ml.train` has produced
    artifacts; falls back to the Phase 3 heuristic otherwise (see
    trust_engine.evaluate — this function never raises for a missing model,
    it simply passes ml_score=None through).

    `include_ml_anomaly` is off by default because it is the expensive part
    and most callers throw it away. Detecting it fits a fresh Isolation Forest
    on that agent's own history — around 340ms — which is fine for one agent
    and ruinous for a list. The estate overview was paying it for all
    nineteen agents on every request and then reporting `evaluation.drift`,
    the heuristic measure, instead: about six seconds of work whose result was
    never read. Only the per-agent detail view surfaces it, so only that view
    asks for it.
    """
    agent = await _load_agent(db, agent_id)
    if agent is None:
        return None

    decisions = await _load_decisions(db, agent_id)
    snapshots = await load_snapshots(db, agent_id)

    ml_score = None
    ml_attribution = None
    ml_anomaly = None

    trust_model = ml_models.load_trust_model()
    if trust_model is not None:
        current_factors = _factor_dict(agent.factors)
        prediction = trust_model.predict(current_factors)
        ml_score, ml_attribution = prediction.score, prediction.attribution

        if include_ml_anomaly:
            history = [_factor_dict(snap.factors) for snap in snapshots if snap.factors] + [
                current_factors
            ]
            anomaly = trust_model.detect_anomaly(history)
            if anomaly is not None:
                ml_anomaly = MLAnomalyResult(detected=anomaly[0], score=anomaly[1])

    evaluation = trust_engine.evaluate(
        agent, decisions, snapshots, now=now, ml_score=ml_score, ml_attribution=ml_attribution
    )
    return agent, evaluation, snapshots, ml_anomaly


async def recompute_agent(
    db: AsyncSession, agent_id: str, *, reason: str = "recompute", now: datetime | None = None
) -> tuple[Agent, TrustEvaluation] | None:
    """Evaluate, persist a snapshot, and move the agent to its new state."""
    loaded = await evaluate_agent(db, agent_id, now=now)
    if loaded is None:
        return None

    agent, evaluation, snapshots, _ml_anomaly = loaded
    previous_score = agent.trust_score

    agent.trust_score = evaluation.score
    agent.trust_delta = round(evaluation.score - previous_score, 2)
    agent.lifecycle = evaluation.lifecycle

    db.add(
        TrustSnapshot(
            agent_id=agent.id,
            score=evaluation.score,
            base_score=evaluation.base_score,
            anomaly_penalty=evaluation.anomaly_penalty,
            factors=evaluation.factors,
            reason=reason,
            captured_at=now or datetime.now(UTC),
        )
    )

    return agent, evaluation


async def recompute_all(
    db: AsyncSession, *, reason: str = "recompute", now: datetime | None = None
) -> list[tuple[Agent, TrustEvaluation]]:
    # Pin the timestamp so every agent in this round shares it. Estate-level
    # trends group snapshots by capture time; per-agent `now()` calls would
    # scatter them across microseconds and make that grouping meaningless.
    now = now or datetime.now(UTC)
    ids = list((await db.execute(select(Agent.id))).scalars().all())

    results = []
    for agent_id in ids:
        outcome = await recompute_agent(db, agent_id, reason=reason, now=now)
        if outcome is not None:
            results.append(outcome)

    await db.commit()
    return results
