from collections import defaultdict

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models import ActivityItem, Agent, Decision, Policy, TrustFactor
from app.models.enums import DecisionOutcome
from app.schemas.governance import (
    ActivityItemRead,
    CompositeTrust,
    DashboardMetric,
    DashboardRead,
    LivePipeline,
    PipelineStage,
    TrustFactorRead,
)

router = APIRouter()

TREND_SAMPLES = 12


def _format_count(value: int) -> str:
    if value >= 1_000_000:
        return f"{value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"{value / 1_000:.1f}K"
    return str(value)


async def _build_pipeline(db: AsyncSession) -> LivePipeline:
    """Render the most recent decision as pipeline stages.

    Phase 2 has no live event stream, so "live" means "latest recorded".
    """
    result = await db.execute(select(Decision).order_by(Decision.decided_at.desc()).limit(1))
    decision = result.unique().scalar_one_or_none()

    if decision is None:
        return LivePipeline(transaction_id="—", stages=[])

    checks = decision.policy_checks
    passed = sum(1 for c in checks if c.passed)
    failed = len(checks) - passed
    approved = decision.outcome == DecisionOutcome.APPROVED

    stages = [
        PipelineStage(
            key="request", label="Agent Request", status="done", detail=decision.agent_name
        ),
        PipelineStage(
            key="trust", label="Trust Engine", status="done", detail=f"Score {decision.trust_score}"
        ),
        PipelineStage(
            key="policy",
            label="Policy Brain",
            status="failed" if failed else "done",
            detail=f"{passed}/{len(checks)} passed",
        ),
        PipelineStage(
            key="simulation",
            label="Simulation Engine",
            status="done",
            detail=f"Risk {decision.risk_score}",
        ),
        PipelineStage(
            key="decision",
            label="Governance Decision",
            status="failed" if decision.outcome == DecisionOutcome.BLOCKED else "done",
            detail=decision.outcome.value.title(),
        ),
        PipelineStage(key="explain", label="Explain AI", status="done"),
        PipelineStage(key="ledger", label="Governance Ledger", status="done"),
        PipelineStage(
            key="execute",
            label="Enterprise System",
            status="done" if approved else "pending",
            detail=None if approved else "Held",
        ),
    ]
    return LivePipeline(transaction_id=decision.id, stages=stages)


@router.get("/dashboard", response_model=DashboardRead, tags=["dashboard"])
async def get_dashboard(db: AsyncSession = Depends(get_db)) -> DashboardRead:
    agent_count = (await db.execute(select(func.count()).select_from(Agent))).scalar_one()
    decisions_today = (
        await db.execute(select(func.coalesce(func.sum(Agent.decisions_today), 0)))
    ).scalar_one()
    avg_trust = (await db.execute(select(func.avg(Agent.trust_score)))).scalar_one() or 0

    evaluations = (
        await db.execute(select(func.coalesce(func.sum(Policy.evaluations_24h), 0)))
    ).scalar_one()
    violations = (
        await db.execute(select(func.coalesce(func.sum(Policy.violations_24h), 0)))
    ).scalar_one()
    compliance = (1 - violations / evaluations) * 100 if evaluations else 100.0

    total_decisions = (await db.execute(select(func.count()).select_from(Decision))).scalar_one()
    explained = (
        await db.execute(select(func.count()).select_from(Decision).where(Decision.rationale != ""))
    ).scalar_one()
    escalated = (
        await db.execute(
            select(func.count())
            .select_from(Decision)
            .where(Decision.outcome == DecisionOutcome.ESCALATED)
        )
    ).scalar_one()

    explainability = (explained / total_decisions * 100) if total_decisions else 0.0
    review_rate = (escalated / total_decisions * 100) if total_decisions else 0.0

    metrics = [
        DashboardMetric(
            key="agents",
            label="Active AI Agents",
            value=str(agent_count),
            tone="secondary",
            icon="bot",
        ),
        DashboardMetric(
            key="decisions",
            label="Protected Decisions Today",
            value=_format_count(int(decisions_today)),
            tone="secondary",
            icon="shield",
        ),
        DashboardMetric(
            key="trust",
            label="Average Trust Score",
            value=str(round(avg_trust)),
            tone="tertiary",
            icon="verified",
        ),
        DashboardMetric(
            key="compliance",
            label="Policy Compliance",
            value=f"{compliance:.2f}%",
            tone="secondary",
            icon="policy",
        ),
        DashboardMetric(
            key="explainability",
            label="Explainability Coverage",
            value=f"{explainability:.1f}%",
            tone="secondary",
            icon="brain",
        ),
        DashboardMetric(
            key="review",
            label="Human Review Rate",
            value=f"{review_rate:.1f}%",
            tone="error",
            icon="gavel",
        ),
    ]

    # Composite trust = each factor averaged across the whole agent estate.
    factor_rows = (await db.execute(select(TrustFactor))).scalars().all()
    grouped: dict[str, list[TrustFactor]] = defaultdict(list)
    for row in factor_rows:
        grouped[row.key].append(row)

    factors = [
        TrustFactorRead(
            key=key,
            label=rows[0].label,
            score=round(sum(r.score for r in rows) / len(rows)),
            weight=rows[0].weight,
        )
        for key, rows in grouped.items()
    ]

    # Trust score recorded against each recent decision, oldest → newest. This is
    # real operational data, but it samples across agents rather than tracking one
    # agent over time — a proper trust history lands with the Trust Engine.
    trend_rows = (
        (
            await db.execute(
                select(Decision.trust_score)
                .order_by(Decision.decided_at.desc())
                .limit(TREND_SAMPLES)
            )
        )
        .scalars()
        .all()
    )
    trend = list(reversed([int(t) for t in trend_rows]))

    activity_rows = (
        (await db.execute(select(ActivityItem).order_by(ActivityItem.at.desc()).limit(8)))
        .scalars()
        .all()
    )

    return DashboardRead(
        metrics=metrics,
        composite_trust=CompositeTrust(
            score=round(avg_trust),
            predicted=None,
            factors=factors,
            trend=trend,
        ),
        live_pipeline=await _build_pipeline(db),
        activity=[ActivityItemRead.model_validate(a) for a in activity_rows],
    )
