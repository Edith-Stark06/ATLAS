"""Database-facing orchestration around the Trust Engine."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Agent, Decision, TrustSnapshot
from app.services import trust_engine
from app.services.trust_engine import TrustEvaluation

SNAPSHOT_HISTORY_LIMIT = 40


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
    db: AsyncSession, agent_id: str, *, now: datetime | None = None
) -> tuple[Agent, TrustEvaluation, list[TrustSnapshot]] | None:
    """Evaluate an agent without persisting anything."""
    agent = await _load_agent(db, agent_id)
    if agent is None:
        return None

    decisions = await _load_decisions(db, agent_id)
    snapshots = await load_snapshots(db, agent_id)
    evaluation = trust_engine.evaluate(agent, decisions, snapshots, now=now)
    return agent, evaluation, snapshots


async def recompute_agent(
    db: AsyncSession, agent_id: str, *, reason: str = "recompute", now: datetime | None = None
) -> tuple[Agent, TrustEvaluation] | None:
    """Evaluate, persist a snapshot, and move the agent to its new state."""
    loaded = await evaluate_agent(db, agent_id, now=now)
    if loaded is None:
        return None

    agent, evaluation, snapshots = loaded
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
