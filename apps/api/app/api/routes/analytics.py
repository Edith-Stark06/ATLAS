from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.analytics import (
    AnalyticsRead,
    BucketRead,
    DayPointRead,
    ExposureRead,
    HotspotRead,
    LatencyRead,
    RateRead,
    ReviewLoadRead,
)
from app.services import analytics_service
from app.services.analytics_engine import Rate

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _rate(rate: Rate) -> RateRead:
    return RateRead(count=rate.count, total=rate.total, percent=rate.percent)


@router.get("", response_model=AnalyticsRead)
async def governance_analytics(
    days: int = Query(30, ge=1, le=analytics_service.MAX_WINDOW_DAYS),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsRead:
    """Aggregate trends across agents, policies and decisions.

    Computed from recorded activity on each request rather than from a
    maintained rollup — a governance dashboard whose numbers can drift from
    the decisions they describe is worse than no dashboard.
    """
    summary = await analytics_service.summary(db, days=days)
    totals = await analytics_service.estate_totals(db)

    return AnalyticsRead(
        window_days=summary.window_days,
        generated_at=summary.generated_at,
        agents=totals.agents,
        decisions_all_time=totals.decisions_all_time,
        agents_without_decisions=totals.agents_without_decisions,
        trust=[BucketRead(label=b.label, count=b.count, share=b.share) for b in summary.trust],
        outcomes=[
            BucketRead(label=b.label, count=b.count, share=b.share) for b in summary.outcomes
        ],
        series=[
            DayPointRead(
                day=p.day,
                approved=p.approved,
                escalated=p.escalated,
                blocked=p.blocked,
                total=p.total,
            )
            for p in summary.series
        ],
        hotspots=[
            HotspotRead(
                policy_id=h.policy_id,
                policy_name=h.policy_name,
                evaluations=h.evaluations,
                restrictions=h.restrictions,
                match_rate=_rate(h.match_rate),
                never_fired=h.never_fired,
            )
            for h in summary.hotspots
        ],
        latency=LatencyRead(
            samples=summary.latency.samples,
            p50=summary.latency.p50,
            p95=summary.latency.p95,
            p99=summary.latency.p99,
            mean=summary.latency.mean,
            max=summary.latency.max,
        ),
        review=ReviewLoadRead(
            escalated=summary.review.escalated,
            total=summary.review.total,
            rate=_rate(summary.review.rate),
            per_day=summary.review.per_day,
        ),
        exposure=ExposureRead(
            moved_usd=summary.exposure.moved_usd,
            withheld_usd=summary.exposure.withheld_usd,
            decisions_with_amount=summary.exposure.decisions_with_amount,
            withheld_share=summary.exposure.withheld_share,
        ),
    )
