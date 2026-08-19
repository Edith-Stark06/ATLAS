"""Unit tests for the Trust Engine.

Pure functions over plain objects — no database, so these run anywhere.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import DecisionOutcome, LifecycleState
from app.services import trust_engine
from app.services.trust_engine import DriftAssessment

NOW = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)


@dataclass
class FakeFactor:
    key: str
    label: str
    score: int
    weight: float


@dataclass
class FakeDecision:
    outcome: DecisionOutcome
    decided_at: datetime


@dataclass
class FakeSnapshot:
    score: int


def factors(**scores: int) -> list[FakeFactor]:
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    return [FakeFactor(k, k.upper(), v, weights.get(k, 1.0)) for k, v in scores.items()]


# --- base score -------------------------------------------------------------


def test_base_score_is_the_weighted_mean():
    # 90*0.5 + 80*0.3 + 70*0.2 = 45 + 24 + 14 = 83
    assert trust_engine.compute_base_score(factors(a=90, b=80, c=70)) == pytest.approx(83.0)


def test_base_score_normalises_weights_that_do_not_sum_to_one():
    """Adding a factor must not silently rescale everyone's score."""
    halved = [FakeFactor("a", "A", 90, 0.25), FakeFactor("b", "B", 80, 0.15)]
    full = [FakeFactor("a", "A", 90, 0.5), FakeFactor("b", "B", 80, 0.3)]
    assert trust_engine.compute_base_score(halved) == pytest.approx(
        trust_engine.compute_base_score(full)
    )


def test_base_score_of_no_factors_is_zero_not_a_crash():
    assert trust_engine.compute_base_score([]) == 0.0


# --- anomaly penalty --------------------------------------------------------


def test_penalty_counts_only_decisions_inside_the_window():
    inside = FakeDecision(DecisionOutcome.BLOCKED, NOW - timedelta(days=1))
    outside = FakeDecision(DecisionOutcome.BLOCKED, NOW - timedelta(days=30))

    penalty, blocked, escalated = trust_engine.compute_anomaly_penalty([inside, outside], now=NOW)

    assert blocked == 1
    assert escalated == 0
    assert penalty == pytest.approx(trust_engine.PENALTY_PER_BLOCKED)


def test_blocked_costs_more_than_escalated():
    assert trust_engine.PENALTY_PER_BLOCKED > trust_engine.PENALTY_PER_ESCALATED


def test_penalty_is_capped():
    many = [FakeDecision(DecisionOutcome.BLOCKED, NOW) for _ in range(50)]
    penalty, _, _ = trust_engine.compute_anomaly_penalty(many, now=NOW)
    assert penalty == trust_engine.MAX_ANOMALY_PENALTY


def test_approved_decisions_carry_no_penalty():
    approved = [FakeDecision(DecisionOutcome.APPROVED, NOW) for _ in range(5)]
    penalty, blocked, escalated = trust_engine.compute_anomaly_penalty(approved, now=NOW)
    assert (penalty, blocked, escalated) == (0.0, 0, 0)


# --- drift ------------------------------------------------------------------


def test_no_history_means_no_drift():
    drift = trust_engine.assess_drift(80, [])
    assert drift.detected is False
    assert drift.baseline is None
    assert drift.samples == 0


def test_drift_is_detected_on_a_sustained_drop():
    history = [FakeSnapshot(90) for _ in range(5)]
    drift = trust_engine.assess_drift(70, history)

    assert drift.detected is True
    assert drift.delta == pytest.approx(-20.0)
    assert drift.baseline == pytest.approx(90.0)


def test_improvement_is_not_drift():
    drift = trust_engine.assess_drift(95, [FakeSnapshot(80) for _ in range(5)])
    assert drift.detected is False
    assert drift.delta > 0


def test_small_dips_are_not_drift():
    drift = trust_engine.assess_drift(89, [FakeSnapshot(90) for _ in range(5)])
    assert drift.detected is False


# --- lifecycle --------------------------------------------------------------

STABLE = DriftAssessment(detected=False, delta=0.5, baseline=90.0, samples=5)
SLIDING = DriftAssessment(detected=True, delta=-12.0, baseline=90.0, samples=5)
RECOVERING = DriftAssessment(detected=False, delta=4.0, baseline=70.0, samples=5)

HIGH_VOLUME = trust_engine.ONBOARDING_MIN_DECISIONS * 10


def test_low_volume_agents_stay_in_onboarding_regardless_of_score():
    state = trust_engine.next_lifecycle(
        score=99, previous=LifecycleState.ONBOARDING, drift=STABLE, decision_volume=1
    )
    assert state is LifecycleState.ONBOARDING


def test_strong_stable_agent_is_trusted():
    state = trust_engine.next_lifecycle(
        score=95, previous=LifecycleState.HEALTHY, drift=STABLE, decision_volume=HIGH_VOLUME
    )
    assert state is LifecycleState.TRUSTED


def test_sliding_agent_becomes_anomaly_even_with_a_good_score():
    """A high absolute score should not mask a steep decline."""
    state = trust_engine.next_lifecycle(
        score=88, previous=LifecycleState.TRUSTED, drift=SLIDING, decision_volume=HIGH_VOLUME
    )
    assert state is LifecycleState.ANOMALY


def test_very_low_score_goes_to_review():
    state = trust_engine.next_lifecycle(
        score=40, previous=LifecycleState.HEALTHY, drift=STABLE, decision_volume=HIGH_VOLUME
    )
    assert state is LifecycleState.REVIEW


def test_improving_agent_passes_through_recovery_before_trusted():
    state = trust_engine.next_lifecycle(
        score=93, previous=LifecycleState.REVIEW, drift=RECOVERING, decision_volume=HIGH_VOLUME
    )
    assert state is LifecycleState.RECOVERY


def test_recovery_is_not_a_dead_end():
    """Once in RECOVERY, a stable agent progresses rather than sticking."""
    state = trust_engine.next_lifecycle(
        score=93, previous=LifecycleState.RECOVERY, drift=STABLE, decision_volume=HIGH_VOLUME
    )
    assert state is LifecycleState.TRUSTED


# --- forecast ---------------------------------------------------------------


def test_forecast_needs_enough_samples():
    assert trust_engine.forecast_series([80.0, 82.0]) is None


def test_forecast_follows_a_rising_trend():
    projected = trust_engine.forecast_series([80.0, 82.0, 84.0, 86.0])
    assert projected is not None and projected > 86


def test_forecast_follows_a_falling_trend():
    projected = trust_engine.forecast_series([90.0, 86.0, 82.0, 78.0])
    assert projected is not None and projected < 78


def test_forecast_is_clamped_to_the_score_range():
    assert trust_engine.forecast_series([97.0, 98.0, 99.0, 100.0]) <= 100
    assert trust_engine.forecast_series([9.0, 6.0, 3.0, 0.0]) >= 0


def test_flat_history_forecasts_the_same_value():
    assert trust_engine.forecast_series([85.0] * 5) == 85
