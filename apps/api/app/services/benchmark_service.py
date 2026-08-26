"""Database side of comparative benchmarking.

Gathers per-agent observations over a window and hands them to the engine.
The window applies to decisions and policy checks alike: comparing one
agent's last week against another's last year would rank them on how long
they had been running.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Decision, PolicyCheck, TrustSnapshot
from app.models.enums import DecisionOutcome
from app.services import analytics_engine, benchmark_engine
from app.services.benchmark_engine import AgentMetrics, ChangeAttribution, Gap, Ranking

FACTOR_LABELS = {
    "behavior": "Behavior Consistency",
    "policy": "Policy Compliance",
    "risk": "Risk Exposure",
    "context": "Context Awareness",
    "history": "Historical Reliability",
}

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 365


class CohortNotFound(LookupError):
    pass


class AgentNotFound(LookupError):
    pass


@dataclass(frozen=True)
class CohortSummary:
    capability: str
    agents: int


@dataclass(frozen=True)
class BenchmarkResult:
    ranking: Ranking
    window_days: int
    #: Per-agent gaps to the cohort leader, keyed by agent id. Empty for the
    #: leader itself, and for a cohort too small to compare.
    gaps: dict[str, list[Gap]]


async def list_cohorts(db: AsyncSession) -> list[CohortSummary]:
    """Every capability with at least one agent, largest cohort first."""
    rows = (await db.execute(select(Agent.capability, Agent.id))).all()

    counts: dict[str, int] = {}
    for capability, _ in rows:
        counts[capability] = counts.get(capability, 0) + 1

    return sorted(
        (CohortSummary(capability=name, agents=count) for name, count in counts.items()),
        key=lambda c: (c.agents, c.capability),
        reverse=True,
    )


async def _metrics_for(db: AsyncSession, agent: Agent, *, since: datetime) -> AgentMetrics:
    decisions = (
        await db.execute(
            select(Decision.outcome, Decision.latency_ms).where(
                Decision.agent_id == agent.id, Decision.decided_at >= since
            )
        )
    ).all()

    checks = (
        (
            await db.execute(
                select(PolicyCheck.passed)
                .join(Decision, Decision.id == PolicyCheck.decision_id)
                .where(Decision.agent_id == agent.id, Decision.decided_at >= since)
            )
        )
        .scalars()
        .all()
    )

    history = (
        (
            await db.execute(
                select(TrustSnapshot.score)
                .where(TrustSnapshot.agent_id == agent.id, TrustSnapshot.captured_at >= since)
                .order_by(TrustSnapshot.captured_at)
            )
        )
        .scalars()
        .all()
    )

    latencies = [row.latency_ms for row in decisions if row.latency_ms is not None]

    return AgentMetrics(
        agent_id=agent.id,
        agent_name=agent.name,
        capability=agent.capability,
        decisions=len(decisions),
        approved=sum(1 for r in decisions if r.outcome is DecisionOutcome.APPROVED),
        escalated=sum(1 for r in decisions if r.outcome is DecisionOutcome.ESCALATED),
        blocked=sum(1 for r in decisions if r.outcome is DecisionOutcome.BLOCKED),
        policy_checks=len(checks),
        policy_passed=sum(1 for passed in checks if passed),
        # p95, matching how latency is reported everywhere else in the system.
        p95_latency_ms=round(analytics_engine.percentile(latencies, 0.95)),
        trust_history=list(history),
    )


async def benchmark_cohort(
    db: AsyncSession, capability: str, *, days: int = DEFAULT_WINDOW_DAYS
) -> BenchmarkResult:
    """Rank every agent doing this job."""
    days = max(1, min(days, MAX_WINDOW_DAYS))
    since = (datetime.now(UTC) - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    agents = (await db.execute(select(Agent).where(Agent.capability == capability))).scalars().all()

    if not agents:
        raise CohortNotFound(f"No agents with capability '{capability}'")

    cohort = [await _metrics_for(db, agent, since=since) for agent in agents]
    ranking = benchmark_engine.rank_cohort(cohort)

    gaps: dict[str, list[Gap]] = {}
    if ranking.comparable and ranking.leader is not None:
        for scored in ranking.scored:
            if scored.agent_id == ranking.leader.agent_id:
                continue
            gaps[scored.agent_id] = benchmark_engine.gaps_to_leader(scored, ranking.leader)

    return BenchmarkResult(ranking=ranking, window_days=days, gaps=gaps)


async def explain_score_change(
    db: AsyncSession, agent_id: str, *, days: int = DEFAULT_WINDOW_DAYS
) -> ChangeAttribution:
    """What moved this agent's trust score over the window.

    Compares the oldest and newest snapshots inside the window rather than the
    last two: consecutive recomputes often differ by nothing, and "nothing
    changed since five minutes ago" is not the question being asked.
    """
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise AgentNotFound(f"Agent '{agent_id}' not found")

    days = max(1, min(days, MAX_WINDOW_DAYS))
    since = datetime.now(UTC) - timedelta(days=days)

    snapshots = (
        (
            await db.execute(
                select(TrustSnapshot)
                .where(TrustSnapshot.agent_id == agent_id, TrustSnapshot.captured_at >= since)
                .order_by(TrustSnapshot.captured_at)
            )
        )
        .scalars()
        .all()
    )

    if len(snapshots) < 2:
        # Not an error: a new agent genuinely has nothing to compare. An empty
        # attribution says so, where a fabricated one would not.
        return benchmark_engine.attribute_change(
            before_factors=[],
            after_factors=[],
            before_score=agent.trust_score,
            after_score=agent.trust_score,
            labels=FACTOR_LABELS,
        )

    first, last = snapshots[0], snapshots[-1]

    return benchmark_engine.attribute_change(
        before_factors=first.factors or [],
        after_factors=last.factors or [],
        before_score=first.score,
        after_score=last.score,
        before_penalty=first.anomaly_penalty or 0.0,
        after_penalty=last.anomaly_penalty or 0.0,
        labels=FACTOR_LABELS,
    )
