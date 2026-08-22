from datetime import date, datetime

from app.schemas.base import ApiModel


class RateRead(ApiModel):
    count: int
    #: The denominator, always sent. A rate rendered without its sample size
    #: makes 1-in-12 look like 1-in-12,000.
    total: int
    percent: float


class BucketRead(ApiModel):
    label: str
    count: int
    #: 0–1.
    share: float


class LatencyRead(ApiModel):
    samples: int
    p50: int
    p95: int
    p99: int
    #: Sent alongside the percentiles, not instead: a mean far from p99 is
    #: itself the finding.
    mean: int
    max: int


class DayPointRead(ApiModel):
    day: date
    approved: int
    escalated: int
    blocked: int
    total: int


class HotspotRead(ApiModel):
    policy_id: str
    policy_name: str
    evaluations: int
    restrictions: int
    match_rate: RateRead
    #: Evaluated enough times to judge, and never once matched. Mis-scoped or
    #: redundant — either way an author should look.
    never_fired: bool


class ReviewLoadRead(ApiModel):
    escalated: int
    total: int
    rate: RateRead
    #: Escalations per day, so review staffing can be sized against it.
    per_day: float


class ExposureRead(ApiModel):
    moved_usd: float
    withheld_usd: float
    #: Actions carrying a monetary value. Others are governed but contribute
    #: nothing to an exposure figure.
    decisions_with_amount: int
    withheld_share: float


class AnalyticsRead(ApiModel):
    window_days: int
    generated_at: datetime

    agents: int
    decisions_all_time: int
    agents_without_decisions: int

    trust: list[BucketRead]
    outcomes: list[BucketRead]
    series: list[DayPointRead]
    hotspots: list[HotspotRead]
    latency: LatencyRead
    review: ReviewLoadRead
    exposure: ExposureRead
