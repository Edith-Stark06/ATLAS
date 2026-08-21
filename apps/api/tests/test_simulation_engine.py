"""Unit tests for the Simulation Engine.

Pure functions over plain values — no database, no trained artifacts.
"""

import pytest

from app.models.enums import DecisionOutcome
from app.services.policy_engine import Effect
from app.services.simulation_engine import (
    ADVERSE_ESCALATION_THRESHOLD,
    RESIDUAL_RISK_FACTOR,
    recommend,
    simulate,
)

APPROVED = DecisionOutcome.APPROVED
ESCALATED = DecisionOutcome.ESCALATED
BLOCKED = DecisionOutcome.BLOCKED


def probs(approved=0.0, escalated=0.0, blocked=0.0) -> dict[DecisionOutcome, float]:
    return {APPROVED: approved, ESCALATED: escalated, BLOCKED: blocked}


# --- policy is a hard constraint --------------------------------------------


def test_a_blocking_rule_beats_a_confident_model():
    """The whole safety argument: a statistical prediction must never unblock
    something the rules explicitly forbid."""
    recommendation, forced, _ = recommend(probs(approved=0.99), Effect.BLOCK)

    assert recommendation is BLOCKED
    assert forced is True


def test_a_review_rule_beats_a_confident_model():
    recommendation, forced, _ = recommend(probs(approved=0.99), Effect.REQUIRE_HUMAN_REVIEW)

    assert recommendation is ESCALATED
    assert forced is True


def test_permissive_rules_defer_to_the_model():
    recommendation, forced, _ = recommend(probs(approved=0.95, escalated=0.05), Effect.ALLOW)

    assert recommendation is APPROVED
    assert forced is False


# --- the model may escalate what the rules permit ----------------------------


def test_model_escalates_above_the_adverse_threshold():
    """Rules allow it, but the model sees risk they do not encode."""
    over = ADVERSE_ESCALATION_THRESHOLD + 0.05
    recommendation, forced, adverse = recommend(
        probs(approved=1 - over, escalated=over), Effect.ALLOW
    )

    assert recommendation is ESCALATED
    assert forced is False
    assert adverse == pytest.approx(over)


def test_model_approves_below_the_adverse_threshold():
    under = ADVERSE_ESCALATION_THRESHOLD - 0.05
    recommendation, _, _ = recommend(probs(approved=1 - under, escalated=under), Effect.ALLOW)

    assert recommendation is APPROVED


def test_adverse_probability_counts_both_non_approval_paths():
    _, _, adverse = recommend(probs(approved=0.6, escalated=0.25, blocked=0.15), Effect.ALLOW)
    assert adverse == pytest.approx(0.4)


# --- probability handling ----------------------------------------------------


def test_probabilities_are_normalised():
    verdict = simulate(
        probabilities={APPROVED: 2.0, ESCALATED: 1.0, BLOCKED: 1.0},
        policy_effect=Effect.ALLOW,
        amount_usd=1000,
        risk_score=20,
    )
    assert sum(o.probability for o in verdict.outcomes) == pytest.approx(1.0, abs=1e-3)


def test_a_missing_class_reads_as_zero_not_a_crash():
    """The classifier only emits classes it saw in training."""
    verdict = simulate(
        probabilities={APPROVED: 1.0},
        policy_effect=Effect.ALLOW,
        amount_usd=500,
        risk_score=10,
    )
    by_outcome = {o.outcome: o for o in verdict.outcomes}
    assert by_outcome[BLOCKED].probability == 0.0
    assert len(verdict.outcomes) == 3


def test_no_signal_spreads_evenly_rather_than_inventing_a_winner():
    verdict = simulate(
        probabilities=probs(),
        policy_effect=Effect.ALLOW,
        amount_usd=100,
        risk_score=50,
    )
    for outcome in verdict.outcomes:
        assert outcome.probability == pytest.approx(1 / 3, abs=1e-3)


# --- financial exposure ------------------------------------------------------


def test_only_approval_moves_money():
    verdict = simulate(
        probabilities=probs(approved=0.5, escalated=0.3, blocked=0.2),
        policy_effect=Effect.ALLOW,
        amount_usd=10_000,
        risk_score=30,
    )
    by_outcome = {o.outcome: o for o in verdict.outcomes}

    assert by_outcome[APPROVED].financial_impact_usd == 10_000
    assert by_outcome[ESCALATED].financial_impact_usd == 0
    assert by_outcome[BLOCKED].financial_impact_usd == 0


def test_exposure_follows_the_recommendation_not_the_raw_probabilities():
    """Once the recommendation is to hold or block, no money moves. Quoting a
    probability-weighted figure there would report an exposure the system is
    actively preventing."""
    verdict = simulate(
        probabilities=probs(approved=0.25, escalated=0.5, blocked=0.25),
        policy_effect=Effect.ALLOW,
        amount_usd=8_000,
        risk_score=30,
    )
    assert verdict.recommendation is ESCALATED  # adverse 0.75 is over threshold
    assert verdict.expected_exposure_usd == 0
    assert verdict.withheld_usd == pytest.approx(8_000)
    # The unpoliced estimate is still reported, so the gap is visible.
    assert verdict.unconstrained_exposure_usd == pytest.approx(2_000)


def test_approval_exposes_the_full_amount():
    verdict = simulate(
        probabilities=probs(approved=0.9, escalated=0.1),
        policy_effect=Effect.ALLOW,
        amount_usd=8_000,
        risk_score=10,
    )
    assert verdict.recommendation is APPROVED
    assert verdict.expected_exposure_usd == pytest.approx(8_000)
    assert verdict.withheld_usd == 0


def test_a_blocking_rule_drops_exposure_to_zero():
    """The case that motivated splitting these two figures: the model is
    confident about approval, but the rules block, so nothing moves."""
    verdict = simulate(
        probabilities=probs(approved=0.67, escalated=0.21, blocked=0.12),
        policy_effect=Effect.BLOCK,
        amount_usd=4_820,
        risk_score=95,
    )
    assert verdict.expected_exposure_usd == 0
    assert verdict.withheld_usd == pytest.approx(4_820)
    assert verdict.unconstrained_exposure_usd == pytest.approx(3_229.4, abs=1)
    assert "No money moves" in " ".join(verdict.explanation)


def test_an_action_with_no_amount_still_gets_a_recommendation():
    """A card freeze has no monetary value but must still be governed."""
    verdict = simulate(
        probabilities=probs(approved=0.9, escalated=0.1),
        policy_effect=Effect.ALLOW,
        amount_usd=None,
        risk_score=8,
    )
    assert verdict.recommendation is APPROVED
    assert verdict.expected_exposure_usd == 0
    assert "No monetary amount" in " ".join(verdict.explanation)


# --- residual risk -----------------------------------------------------------


def test_residual_risk_decreases_along_safer_paths():
    verdict = simulate(
        probabilities=probs(approved=0.5, escalated=0.3, blocked=0.2),
        policy_effect=Effect.ALLOW,
        amount_usd=1_000,
        risk_score=80,
    )
    by_outcome = {o.outcome: o for o in verdict.outcomes}

    assert by_outcome[APPROVED].risk_score == 80  # full risk taken
    assert by_outcome[BLOCKED].risk_score == 0  # action never happens
    assert 0 < by_outcome[ESCALATED].risk_score < 80


def test_residual_risk_factors_are_ordered_sensibly():
    assert (
        RESIDUAL_RISK_FACTOR[BLOCKED]
        < RESIDUAL_RISK_FACTOR[ESCALATED]
        < RESIDUAL_RISK_FACTOR[APPROVED]
    )


# --- compliance flags --------------------------------------------------------


def test_approval_is_non_compliant_when_a_rule_forbids_it():
    """Still shown as a prediction — it is a real possibility the model sees,
    just not one the rules permit."""
    verdict = simulate(
        probabilities=probs(approved=0.7, blocked=0.3),
        policy_effect=Effect.BLOCK,
        amount_usd=5_000,
        risk_score=90,
    )
    by_outcome = {o.outcome: o for o in verdict.outcomes}

    assert by_outcome[APPROVED].compliant is False
    assert by_outcome[BLOCKED].compliant is True
    assert verdict.recommendation is BLOCKED


def test_every_path_is_compliant_when_rules_permit():
    verdict = simulate(
        probabilities=probs(approved=0.8, escalated=0.2),
        policy_effect=Effect.ALLOW,
        amount_usd=100,
        risk_score=5,
    )
    assert all(o.compliant for o in verdict.outcomes)


# --- verdict shape -----------------------------------------------------------


def test_exactly_one_outcome_is_recommended():
    verdict = simulate(
        probabilities=probs(approved=0.4, escalated=0.35, blocked=0.25),
        policy_effect=Effect.ALLOW,
        amount_usd=2_000,
        risk_score=40,
    )
    assert sum(1 for o in verdict.outcomes if o.recommended) == 1


def test_confidence_is_the_probability_of_the_recommended_path():
    verdict = simulate(
        probabilities=probs(approved=0.62, escalated=0.28, blocked=0.10),
        policy_effect=Effect.ALLOW,
        amount_usd=1_000,
        risk_score=20,
    )
    assert verdict.confidence == pytest.approx(62.0, abs=0.1)


def test_explanation_names_the_binding_rule_when_policy_decides():
    verdict = simulate(
        probabilities=probs(approved=0.99),
        policy_effect=Effect.BLOCK,
        amount_usd=1_000,
        risk_score=95,
    )
    joined = " ".join(verdict.explanation).lower()

    assert verdict.policy_forced is True
    assert "binding" in joined
    assert "cannot override" in joined
