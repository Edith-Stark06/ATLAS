"""Aggregate statistics over governance activity.

Pure functions over plain values — no database — so the arithmetic can be
tested exhaustively, including the edge cases that make aggregate views lie:
an empty estate, a single sample, a policy that has never fired.

Two deliberate choices run through this module:

- **Percentiles, not means.** ATLAS sits in the critical path of an action
  that is about to happen, so the number that matters is what the slowest
  requests cost, not the average. A mean latency of 40ms hides a p99 of 900ms,
  and the p99 is the one that times out a payment.
- **Rates carry their denominator.** "8% violation rate" over 12 decisions is
  noise; over 12,000 it is a finding. Every rate here travels with the count
  it was computed from so a caller cannot render the first as though it were
  the second.
"""

import math
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from app.models.enums import DecisionOutcome

#: Bands the estate's trust scores are bucketed into for distribution views.
#: Lower bound inclusive, upper bound inclusive — contiguous with no gaps, so
#: every score in 0–100 lands in exactly one band.
TRUST_BANDS: list[tuple[str, int, int]] = [
    ("restricted", 0, 49),
    ("watch", 50, 69),
    ("healthy", 70, 89),
    ("trusted", 90, 100),
]


@dataclass(frozen=True)
class Rate:
    """A proportion that cannot be read without its sample size."""

    count: int
    total: int

    @property
    def value(self) -> float:
        """0.0 when there is nothing to divide — not an error, and not 1.0."""
        return round(self.count / self.total, 4) if self.total else 0.0

    @property
    def percent(self) -> float:
        return round(self.value * 100, 2)


@dataclass(frozen=True)
class Bucket:
    label: str
    count: int
    #: Share of the whole, 0–1.
    share: float


@dataclass(frozen=True)
class LatencyProfile:
    """What the governance gate costs the actions passing through it."""

    samples: int
    p50: int
    p95: int
    p99: int
    #: Kept alongside the percentiles rather than instead of them, so the two
    #: can be compared — a mean far below p95 is itself the finding.
    mean: int
    max: int


@dataclass(frozen=True)
class DayPoint:
    day: date
    approved: int
    escalated: int
    blocked: int

    @property
    def total(self) -> int:
        return self.approved + self.escalated + self.blocked


@dataclass(frozen=True)
class PolicyHotspot:
    policy_id: str
    policy_name: str
    evaluations: int
    matches: int
    restrictions: int
    match_rate: Rate
    #: True when the rule was evaluated but never once matched over the window.
    #: Either mis-scoped or redundant; both are worth an author's attention.
    never_fired: bool


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile.

    Nearest-rank rather than interpolated: every value returned is a
    measurement that actually occurred. An interpolated p99 of 412ms that no
    request ever took is a worse answer for a latency budget than a real one.
    """
    if not values:
        return 0.0
    if not 0 <= q <= 1:
        raise ValueError("q must be between 0 and 1")

    ordered = sorted(values)
    # Nearest-rank: ceil(q * n), clamped to a valid 1-based index. q=0 gives
    # the smallest sample rather than index 0 of an empty rank.
    rank = math.ceil(q * len(ordered))
    return float(ordered[max(1, min(len(ordered), rank)) - 1])


def latency_profile(latencies: list[int]) -> LatencyProfile:
    """Percentile summary of governance overhead.

    Returns zeros rather than raising on no samples: an estate with no
    decisions yet has no latency, which is different from an error.
    """
    if not latencies:
        return LatencyProfile(samples=0, p50=0, p95=0, p99=0, mean=0, max=0)

    return LatencyProfile(
        samples=len(latencies),
        p50=round(percentile(latencies, 0.50)),
        p95=round(percentile(latencies, 0.95)),
        p99=round(percentile(latencies, 0.99)),
        mean=round(sum(latencies) / len(latencies)),
        max=max(latencies),
    )


def trust_distribution(scores: list[int]) -> list[Bucket]:
    """Estate trust bucketed into bands.

    Every band is returned even when empty. Dropping empty bands would make
    "no agents are restricted" look identical to "the restricted band does not
    exist", and the first is the fact worth seeing.
    """
    total = len(scores)
    counts = Counter(band_for(score) for score in scores)

    return [
        Bucket(
            label=label,
            count=counts.get(label, 0),
            share=round(counts.get(label, 0) / total, 4) if total else 0.0,
        )
        for label, _, _ in TRUST_BANDS
    ]


def band_for(score: int) -> str:
    for label, low, high in TRUST_BANDS:
        if low <= score <= high:
            return label
    # Out of range: clamp rather than invent a band, and let the caller see it
    # land in the nearest real one.
    return TRUST_BANDS[0][0] if score < 0 else TRUST_BANDS[-1][0]


def outcome_mix(outcomes: list[DecisionOutcome]) -> list[Bucket]:
    """Share of each verdict. Every outcome appears, including zeroes."""
    total = len(outcomes)
    counts = Counter(outcomes)

    return [
        Bucket(
            label=outcome.value,
            count=counts.get(outcome, 0),
            share=round(counts.get(outcome, 0) / total, 4) if total else 0.0,
        )
        for outcome in DecisionOutcome
    ]


def daily_series(
    rows: list[tuple[datetime, DecisionOutcome]],
    *,
    days: int,
    today: date | None = None,
) -> list[DayPoint]:
    """One point per day over the window, including days with no activity.

    Gap-filling matters: a chart that silently skips quiet days compresses the
    x-axis and makes a two-week lull look like continuous traffic.
    """
    end = today or datetime.now(UTC).date()
    start = end - timedelta(days=days - 1)

    tally: dict[date, Counter] = {
        start + timedelta(days=offset): Counter() for offset in range(days)
    }

    for moment, outcome in rows:
        # Timestamps are stored UTC-aware; a naive one is treated as UTC rather
        # than silently bucketed by the server's local day.
        aware = moment if moment.tzinfo else moment.replace(tzinfo=UTC)
        day = aware.astimezone(UTC).date()
        if day in tally:
            tally[day][outcome] += 1

    return [
        DayPoint(
            day=day,
            approved=counts.get(DecisionOutcome.APPROVED, 0),
            escalated=counts.get(DecisionOutcome.ESCALATED, 0),
            blocked=counts.get(DecisionOutcome.BLOCKED, 0),
        )
        for day, counts in sorted(tally.items())
    ]


def policy_hotspots(
    rows: list[tuple[str, str, bool]],
    *,
    min_evaluations: int = 1,
) -> list[PolicyHotspot]:
    """Per-policy match statistics, most-restrictive first.

    `rows` is (policy_id, policy_name, passed) — one per recorded check.
    `passed=False` means the policy restricted the action.

    `never_fired` is only claimed once a policy has actually been evaluated
    enough times to mean something. A rule added yesterday has not had a
    chance to fire, and labelling it dead would send an author to delete a
    rule that is working correctly.
    """
    evaluations: Counter[str] = Counter()
    restrictions: Counter[str] = Counter()
    names: dict[str, str] = {}

    for policy_id, policy_name, passed in rows:
        evaluations[policy_id] += 1
        names[policy_id] = policy_name
        if not passed:
            restrictions[policy_id] += 1

    hotspots = [
        PolicyHotspot(
            policy_id=policy_id,
            policy_name=names[policy_id],
            evaluations=total,
            matches=restrictions[policy_id],
            restrictions=restrictions[policy_id],
            match_rate=Rate(count=restrictions[policy_id], total=total),
            never_fired=restrictions[policy_id] == 0 and total >= min_evaluations,
        )
        for policy_id, total in evaluations.items()
    ]

    # Most restrictive first, then by volume — a rule blocking 40% of a large
    # population outranks one blocking 100% of three decisions.
    return sorted(
        hotspots,
        key=lambda h: (h.match_rate.value, h.evaluations),
        reverse=True,
    )


@dataclass(frozen=True)
class ReviewLoad:
    """What governance is asking humans to do."""

    escalated: int
    total: int
    rate: Rate
    #: Decisions escalated per day over the window, so staffing can be sized
    #: against it rather than against a raw total.
    per_day: float


def review_load(series: list[DayPoint]) -> ReviewLoad:
    escalated = sum(point.escalated for point in series)
    total = sum(point.total for point in series)
    days = len(series) or 1

    return ReviewLoad(
        escalated=escalated,
        total=total,
        rate=Rate(count=escalated, total=total),
        per_day=round(escalated / days, 2),
    )


@dataclass(frozen=True)
class ExposureSummary:
    """The money story, which is the point of the product."""

    #: Total value of actions that were approved and therefore moved.
    moved_usd: float
    #: Value of actions that were escalated or blocked, so did not move.
    withheld_usd: float
    decisions_with_amount: int

    @property
    def withheld_share(self) -> float:
        total = self.moved_usd + self.withheld_usd
        return round(self.withheld_usd / total, 4) if total else 0.0


def exposure_summary(rows: list[tuple[DecisionOutcome, float | None]]) -> ExposureSummary:
    """Split recorded value by whether governance let it through.

    Decisions with no amount are counted in neither total — a card freeze is
    a real governed action but contributes nothing to an exposure figure, and
    treating its absent amount as zero would drag the averages down.
    """
    moved = 0.0
    withheld = 0.0
    counted = 0

    for outcome, amount in rows:
        if amount is None:
            continue
        counted += 1
        if outcome is DecisionOutcome.APPROVED:
            moved += amount
        else:
            withheld += amount

    return ExposureSummary(
        moved_usd=round(moved, 2),
        withheld_usd=round(withheld, 2),
        decisions_with_amount=counted,
    )


@dataclass(frozen=True)
class AnalyticsSummary:
    window_days: int
    generated_at: datetime
    trust: list[Bucket] = field(default_factory=list)
    outcomes: list[Bucket] = field(default_factory=list)
    series: list[DayPoint] = field(default_factory=list)
    hotspots: list[PolicyHotspot] = field(default_factory=list)
    latency: LatencyProfile = field(default_factory=lambda: LatencyProfile(0, 0, 0, 0, 0, 0))
    review: ReviewLoad = field(default_factory=lambda: ReviewLoad(0, 0, Rate(0, 0), 0.0))
    exposure: ExposureSummary = field(default_factory=lambda: ExposureSummary(0.0, 0.0, 0))
