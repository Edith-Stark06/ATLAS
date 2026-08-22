"""Unit tests for the analytics aggregations.

Aggregate views are where quiet lies live: an empty estate that renders as
100%, a chart that skips silent days, a "dead rule" label on a policy that
shipped yesterday. These test the edges rather than the happy path.
"""

from datetime import UTC, date, datetime

import pytest

from app.models.enums import DecisionOutcome
from app.services.analytics_engine import (
    Rate,
    band_for,
    daily_series,
    exposure_summary,
    latency_profile,
    outcome_mix,
    percentile,
    policy_hotspots,
    review_load,
    trust_distribution,
)

APPROVED = DecisionOutcome.APPROVED
ESCALATED = DecisionOutcome.ESCALATED
BLOCKED = DecisionOutcome.BLOCKED

TODAY = date(2026, 8, 22)


# --- percentiles -------------------------------------------------------------


def test_percentile_returns_a_value_that_actually_occurred():
    """Nearest-rank, not interpolated: an interpolated p99 nobody ever
    measured is a worse answer for a latency budget than a real one."""
    values = [10, 20, 30, 40, 50]
    assert percentile(values, 0.5) in values
    assert percentile(values, 0.99) in values


def test_percentiles_are_ordered():
    values = list(range(1, 101))
    assert percentile(values, 0.5) <= percentile(values, 0.95) <= percentile(values, 0.99)


def test_percentile_of_one_sample_is_that_sample():
    for q in (0.0, 0.5, 0.95, 1.0):
        assert percentile([7], q) == 7


def test_percentile_of_nothing_is_zero_not_an_error():
    """An estate with no decisions has no latency. That is not a failure."""
    assert percentile([], 0.95) == 0.0


def test_percentile_does_not_care_about_input_order():
    assert percentile([50, 10, 30, 20, 40], 0.5) == percentile([10, 20, 30, 40, 50], 0.5)


def test_p100_is_the_maximum():
    assert percentile([3, 1, 2], 1.0) == 3


def test_an_out_of_range_quantile_is_rejected():
    with pytest.raises(ValueError):
        percentile([1, 2, 3], 1.5)


# --- latency -----------------------------------------------------------------


def test_a_single_outlier_drags_the_mean_but_not_the_percentiles():
    """Why both are kept. One 5-second request among a hundred 10ms ones
    sextuples the mean while p99 correctly stays at 10 — only 1% is slower.
    Reporting the mean alone would invent a latency problem."""
    profile = latency_profile([10] * 99 + [5000])

    assert profile.p99 == 10
    assert profile.mean == 60
    assert profile.max == 5000


def test_percentiles_surface_a_tail_the_mean_hides():
    """The converse, and the reason p95 is reported at all: a 5% slow tail
    barely moves the mean but is exactly what times out a payment."""
    profile = latency_profile([10] * 95 + [5000] * 5)

    assert profile.p95 == 10
    assert profile.p99 == 5000
    assert profile.samples == 100


def test_an_empty_latency_profile_is_all_zeros():
    profile = latency_profile([])
    assert (profile.samples, profile.p50, profile.p95, profile.max) == (0, 0, 0, 0)


# --- rates carry their denominator -------------------------------------------


def test_a_rate_over_nothing_is_zero_not_one():
    """0/0 rendering as 100% would show a pristine estate as fully in
    violation, or the reverse."""
    assert Rate(count=0, total=0).value == 0.0
    assert Rate(count=0, total=0).percent == 0.0


def test_a_rate_exposes_the_sample_it_came_from():
    """8% over 12 decisions is noise; over 12,000 it is a finding."""
    rate = Rate(count=1, total=12)
    assert rate.total == 12
    assert rate.percent == pytest.approx(8.33, abs=0.01)


# --- trust distribution ------------------------------------------------------


@pytest.mark.parametrize(
    "score,band",
    [
        (0, "restricted"),
        (49, "restricted"),
        (50, "watch"),
        (69, "watch"),
        (70, "healthy"),
        (89, "healthy"),
        (90, "trusted"),
        (100, "trusted"),
    ],
)
def test_bands_are_contiguous_with_no_gaps(score, band):
    assert band_for(score) == band


def test_every_score_in_range_lands_in_exactly_one_band():
    buckets = trust_distribution(list(range(0, 101)))
    assert sum(b.count for b in buckets) == 101


def test_empty_bands_are_still_reported():
    """ "No agents are restricted" must not look like "that band does not
    exist"."""
    buckets = trust_distribution([95, 96, 97])
    labels = {b.label for b in buckets}

    assert labels == {"restricted", "watch", "healthy", "trusted"}
    assert next(b for b in buckets if b.label == "restricted").count == 0


def test_an_empty_estate_does_not_divide_by_zero():
    buckets = trust_distribution([])
    assert all(b.count == 0 and b.share == 0.0 for b in buckets)


def test_shares_sum_to_one():
    buckets = trust_distribution([10, 55, 75, 95, 99])
    assert sum(b.share for b in buckets) == pytest.approx(1.0)


# --- outcome mix -------------------------------------------------------------


def test_every_outcome_appears_even_at_zero():
    """A day with no blocks should show "blocked: 0", not omit the row."""
    buckets = outcome_mix([APPROVED, APPROVED])
    assert {b.label for b in buckets} == {"approved", "escalated", "blocked"}
    assert next(b for b in buckets if b.label == "blocked").count == 0


def test_outcome_mix_of_nothing_is_all_zero():
    assert all(b.count == 0 for b in outcome_mix([]))


# --- daily series ------------------------------------------------------------


def test_quiet_days_are_filled_in_not_skipped():
    """Skipping silent days compresses the x-axis and makes a lull look like
    continuous traffic."""
    rows = [(datetime(2026, 8, 22, 9, tzinfo=UTC), APPROVED)]
    series = daily_series(rows, days=7, today=TODAY)

    assert len(series) == 7
    assert sum(p.total for p in series) == 1
    assert series[-1].day == TODAY


def test_the_series_is_in_chronological_order():
    series = daily_series([], days=5, today=TODAY)
    assert [p.day for p in series] == sorted(p.day for p in series)


def test_activity_outside_the_window_is_excluded():
    old = datetime(2026, 1, 1, tzinfo=UTC)
    series = daily_series([(old, BLOCKED)], days=7, today=TODAY)

    assert sum(p.total for p in series) == 0


def test_a_naive_timestamp_is_bucketed_as_utc():
    """Otherwise the day boundary silently follows the server's timezone and
    a decision lands on the wrong date."""
    naive = datetime(2026, 8, 22, 23, 30)
    aware = datetime(2026, 8, 22, 23, 30, tzinfo=UTC)

    assert daily_series([(naive, APPROVED)], days=3, today=TODAY) == daily_series(
        [(aware, APPROVED)], days=3, today=TODAY
    )


def test_outcomes_are_counted_into_the_right_column():
    rows = [
        (datetime(2026, 8, 22, 1, tzinfo=UTC), APPROVED),
        (datetime(2026, 8, 22, 2, tzinfo=UTC), BLOCKED),
        (datetime(2026, 8, 22, 3, tzinfo=UTC), BLOCKED),
    ]
    today_point = daily_series(rows, days=3, today=TODAY)[-1]

    assert (today_point.approved, today_point.escalated, today_point.blocked) == (1, 0, 2)


# --- policy hotspots ---------------------------------------------------------


def test_hotspots_rank_by_restriction_rate():
    rows = (
        [("pol-a", "Rarely", True)] * 99
        + [("pol-a", "Rarely", False)]
        + [("pol-b", "Often", False)] * 5
        + [("pol-b", "Often", True)] * 5
    )
    hotspots = policy_hotspots(rows)

    assert hotspots[0].policy_id == "pol-b"


def test_a_rule_that_never_matched_is_flagged():
    """Either mis-scoped or redundant — both worth an author's attention."""
    rows = [("pol-dead", "Never Fires", True)] * 50
    hotspot = policy_hotspots(rows)[0]

    assert hotspot.never_fired is True
    assert hotspot.matches == 0


def test_a_rule_that_has_fired_is_not_flagged_as_dead():
    rows = [("pol-live", "Fires", True)] * 49 + [("pol-live", "Fires", False)]
    assert policy_hotspots(rows)[0].never_fired is False


def test_a_barely_evaluated_rule_is_not_called_dead():
    """A rule added yesterday has not had a chance to fire. Labelling it dead
    would send an author to delete something that works."""
    rows = [("pol-new", "Just Added", True)] * 2
    hotspot = policy_hotspots(rows, min_evaluations=25)[0]

    assert hotspot.never_fired is False


def test_hotspots_count_every_evaluation_not_just_the_failures():
    rows = [("pol-a", "A", True)] * 8 + [("pol-a", "A", False)] * 2
    hotspot = policy_hotspots(rows)[0]

    assert hotspot.evaluations == 10
    assert hotspot.match_rate.percent == 20.0


def test_no_checks_yields_no_hotspots():
    assert policy_hotspots([]) == []


# --- review load -------------------------------------------------------------


def test_review_load_reports_a_daily_rate_for_staffing():
    rows = [(datetime(2026, 8, 20, 9, tzinfo=UTC), ESCALATED)] * 14
    load = review_load(daily_series(rows, days=7, today=TODAY))

    assert load.escalated == 14
    assert load.per_day == pytest.approx(2.0)


def test_review_load_over_an_empty_window_is_zero():
    load = review_load(daily_series([], days=7, today=TODAY))
    assert load.escalated == 0
    assert load.rate.value == 0.0
    assert load.per_day == 0.0


# --- exposure ----------------------------------------------------------------


def test_only_approved_value_counts_as_moved():
    summary = exposure_summary([(APPROVED, 100.0), (BLOCKED, 900.0)])

    assert summary.moved_usd == 100.0
    assert summary.withheld_usd == 900.0


def test_escalated_value_is_withheld_not_moved():
    """An escalation has not run yet, so its money has not moved."""
    summary = exposure_summary([(ESCALATED, 500.0)])

    assert summary.moved_usd == 0.0
    assert summary.withheld_usd == 500.0


def test_actions_without_an_amount_are_excluded_from_both_totals():
    """A card freeze is a real governed action but contributes nothing to an
    exposure figure; counting its absent amount as zero would drag averages."""
    summary = exposure_summary([(APPROVED, None), (APPROVED, 100.0)])

    assert summary.decisions_with_amount == 1
    assert summary.moved_usd == 100.0


def test_withheld_share_of_nothing_is_zero():
    assert exposure_summary([]).withheld_share == 0.0


def test_withheld_share_is_a_proportion_of_the_whole():
    summary = exposure_summary([(APPROVED, 250.0), (BLOCKED, 750.0)])
    assert summary.withheld_share == pytest.approx(0.75)
