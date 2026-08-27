"""Database side of capacity planning.

Reuses the benchmark's cohort gathering rather than re-deriving throughput
and quality independently. Two subsystems computing "how good is this agent"
from the same records by different routes would drift, and the capacity plan
would start recommending growth for an agent the benchmark screen shows
failing.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.services import benchmark_engine, benchmark_service, capacity_engine
from app.services.capacity_engine import AgentCapacity, CapacityPlan

DEFAULT_WINDOW_DAYS = benchmark_service.DEFAULT_WINDOW_DAYS
MAX_WINDOW_DAYS = benchmark_service.MAX_WINDOW_DAYS

#: Widest growth the endpoint will project. Beyond this the extrapolation is
#: fantasy — every rate in the plan was measured at today's volume.
MAX_MULTIPLIER = 20.0


class CohortNotFound(LookupError):
    pass


def _criterion(scored, key: str) -> float:
    """One criterion's score, or 0 when absent.

    0 rather than a neutral default: a missing safety score must fail the
    floor, never quietly pass it.
    """
    found = scored.criterion(key)
    return found.score if found else 0.0


async def plan_capacity(
    db: AsyncSession,
    capability: str,
    *,
    multiplier: float,
    days: int = DEFAULT_WINDOW_DAYS,
    reviewer_days_available: float,
    review_minutes: float = capacity_engine.DEFAULT_REVIEW_MINUTES,
) -> CapacityPlan:
    """Project what growing this job would demand of governance."""
    days = max(1, min(days, MAX_WINDOW_DAYS))
    multiplier = max(1.0, min(multiplier, MAX_MULTIPLIER))

    try:
        observed = await benchmark_service.cohort_metrics(db, capability, days=days)
    except benchmark_service.CohortNotFound as exc:
        raise CohortNotFound(str(exc)) from exc

    cohort: list[AgentCapacity] = []
    for metrics in observed:
        scored = benchmark_engine.score_agent(metrics)
        cohort.append(
            AgentCapacity(
                agent_id=metrics.agent_id,
                agent_name=metrics.agent_name,
                decisions=metrics.decisions,
                escalated=metrics.escalated,
                blocked=metrics.blocked,
                p95_latency_ms=metrics.p95_latency_ms,
                composite=scored.composite,
                security=_criterion(scored, "security"),
                compliance=_criterion(scored, "compliance"),
                thin_evidence=scored.thin_evidence,
            )
        )

    return capacity_engine.build_plan(
        capability=capability,
        cohort=cohort,
        window_days=days,
        multiplier=multiplier,
        reviewer_days_available=reviewer_days_available,
        review_minutes=review_minutes,
    )
