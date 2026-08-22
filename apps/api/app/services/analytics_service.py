"""Database side of governance analytics.

Read-only. Every figure is computed from recorded activity at request time
rather than from a maintained rollup table: a governance dashboard whose
numbers can drift from the decisions they describe is worse than no
dashboard, and at this scale the aggregate queries are cheap.

The window is applied in SQL, not in Python. Pulling every decision ever
recorded across the wire to count last week's would work fine on seed data
and fall over on a real estate.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Decision, PolicyCheck
from app.services import analytics_engine
from app.services.analytics_engine import AnalyticsSummary

#: Below this many evaluations a policy is too young to call dead. Chosen so a
#: rule added mid-window is not reported as redundant on its first day.
DEAD_RULE_THRESHOLD = 20

#: Widest window the API will serve. Bounded because the queries scan
#: decisions, and an unbounded `days` would let one request read the table.
MAX_WINDOW_DAYS = 365


async def summary(db: AsyncSession, *, days: int = 30) -> AnalyticsSummary:
    """Everything the analytics screen needs, in one pass."""
    days = max(1, min(days, MAX_WINDOW_DAYS))
    now = datetime.now(UTC)
    since = now - timedelta(days=days - 1)
    # Start of that day, so a 7-day window is seven whole days rather than
    # six-and-a-fraction depending on when it is asked for.
    since = since.replace(hour=0, minute=0, second=0, microsecond=0)

    decision_rows = (
        await db.execute(
            select(
                Decision.decided_at,
                Decision.outcome,
                Decision.latency_ms,
                Decision.amount_usd,
            ).where(Decision.decided_at >= since)
        )
    ).all()

    scores = list((await db.execute(select(Agent.trust_score))).scalars().all())

    # Joined to decisions so the window applies to checks too — otherwise a
    # policy's match rate would mix last week's traffic with last year's.
    check_rows = (
        await db.execute(
            select(PolicyCheck.policy_id, PolicyCheck.policy_name, PolicyCheck.passed)
            .join(Decision, Decision.id == PolicyCheck.decision_id)
            .where(Decision.decided_at >= since)
        )
    ).all()

    series = analytics_engine.daily_series(
        [(row.decided_at, row.outcome) for row in decision_rows],
        days=days,
        today=now.date(),
    )

    return AnalyticsSummary(
        window_days=days,
        generated_at=now,
        trust=analytics_engine.trust_distribution(scores),
        outcomes=analytics_engine.outcome_mix([row.outcome for row in decision_rows]),
        series=series,
        hotspots=analytics_engine.policy_hotspots(
            [(row.policy_id, row.policy_name, row.passed) for row in check_rows],
            min_evaluations=DEAD_RULE_THRESHOLD,
        ),
        latency=analytics_engine.latency_profile(
            [row.latency_ms for row in decision_rows if row.latency_ms is not None]
        ),
        review=analytics_engine.review_load(series),
        exposure=analytics_engine.exposure_summary(
            [
                (row.outcome, float(row.amount_usd) if row.amount_usd is not None else None)
                for row in decision_rows
            ]
        ),
    )


@dataclass(frozen=True)
class EstateTotals:
    agents: int
    decisions_all_time: int
    #: Agents that have never had a decision recorded. Not idle — unexercised,
    #: which means their trust score rests on seeded factors rather than on
    #: anything the system has observed.
    agents_without_decisions: int


async def estate_totals(db: AsyncSession) -> EstateTotals:
    agents = (await db.execute(select(func.count(Agent.id)))).scalar_one()
    decisions = (await db.execute(select(func.count(Decision.id)))).scalar_one()

    active = (await db.execute(select(func.count(func.distinct(Decision.agent_id))))).scalar_one()

    return EstateTotals(
        agents=agents or 0,
        decisions_all_time=decisions or 0,
        agents_without_decisions=max(0, (agents or 0) - (active or 0)),
    )
