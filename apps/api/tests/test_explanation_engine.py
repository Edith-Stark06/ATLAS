"""Unit tests for the Explanation Engine.

The counterfactual is the part worth testing hard: it is the only output here
that makes a claim about a decision that was *not* made, so it is the only one
that can be confidently wrong.
"""

import pytest

from app.models.enums import DecisionOutcome
from app.services.explanation_engine import (
    SEARCHABLE_FIELDS,
    Condition,
    ConditionResult,
    condition_boundary,
    drivers_from_attribution,
    headline,
    model_counterfactual,
    model_counterfactuals,
    policy_counterfactuals,
)
from app.services.policy_engine import Operator

APPROVED = DecisionOutcome.APPROVED
ESCALATED = DecisionOutcome.ESCALATED
BLOCKED = DecisionOutcome.BLOCKED


def matched(field: str, operator: Operator, value, actual):
    condition = Condition(field=field, operator=operator, value=value)
    return condition, ConditionResult(condition=condition, matched=True, actual=actual)


# --- policy boundaries are exact ---------------------------------------------


def test_a_greater_than_rule_reports_the_value_that_stops_it():
    """`risk_score > 90` matched at 95 — 90 itself no longer matches."""
    condition, result = matched("risk_score", Operator.GT, 90, 95)
    cf = condition_boundary(condition, result.actual)

    assert cf is not None
    assert cf.threshold == 90
    assert cf.direction == "at most"
    assert cf.exact is True


def test_a_greater_or_equal_rule_steps_below_the_boundary():
    """`risk_score >= 90` still matches at 90, so the answer is 89."""
    condition, result = matched("risk_score", Operator.GTE, 90, 95)
    cf = condition_boundary(condition, result.actual)

    assert cf.threshold == 89
    assert cf.direction == "at most"


def test_a_less_than_rule_reports_the_value_that_stops_it():
    condition, result = matched("trust_score", Operator.LT, 70, 55)
    cf = condition_boundary(condition, result.actual)

    assert cf.threshold == 70
    assert cf.direction == "at least"


def test_a_less_or_equal_rule_steps_above_the_boundary():
    condition, result = matched("trust_score", Operator.LTE, 70, 55)
    cf = condition_boundary(condition, result.actual)

    assert cf.threshold == 71
    assert cf.direction == "at least"


def test_a_float_field_steps_by_cents_not_by_one():
    """Stepping a money threshold by 1 would report a boundary a whole dollar
    away from the real one."""
    condition, result = matched("amount_usd", Operator.GTE, 5000, 9000)
    cf = condition_boundary(condition, result.actual)

    assert cf.threshold == pytest.approx(4999.99)


def test_the_actual_value_is_carried_through():
    condition, result = matched("risk_score", Operator.GT, 90, 95)
    assert condition_boundary(condition, result.actual).current == 95


# --- what has no exact boundary ----------------------------------------------


@pytest.mark.parametrize("operator", [Operator.IN, Operator.NOT_IN, Operator.EQ, Operator.NEQ])
def test_non_ordered_operators_get_no_counterfactual(operator):
    """Set membership has no "just outside" value. Inventing one would be
    worse than saying nothing."""
    condition = Condition(field="capability", operator=operator, value=["Payments"])
    assert condition_boundary(condition, "Payments") is None


def test_a_boolean_threshold_is_not_treated_as_a_number():
    """`True` is an int in Python; arithmetic on it would produce nonsense."""
    condition = Condition(field="risk_score", operator=Operator.GT, value=True)
    assert condition_boundary(condition, 1) is None


# --- collecting policy counterfactuals ---------------------------------------


def test_every_matched_condition_is_reported():
    """Under `all`, breaking any one condition is sufficient — an operator
    should see the whole set, not an arbitrary pick."""
    pairs = [
        matched("risk_score", Operator.GT, 90, 95),
        matched("amount_usd", Operator.GTE, 5000, 9000),
    ]
    cfs = policy_counterfactuals(pairs)

    assert {c.field for c in cfs} == {"risk_score", "amount_usd"}


def test_unmatched_conditions_are_skipped():
    """A condition that did not fire is not why the action was restricted."""
    condition = Condition(field="risk_score", operator=Operator.GT, value=90)
    pairs = [(condition, ConditionResult(condition=condition, matched=False, actual=10))]

    assert policy_counterfactuals(pairs) == []


# --- model counterfactuals ---------------------------------------------------


def approve_below(field: str, cutoff: float):
    """A model that approves when `field` is under `cutoff`."""

    def predict(features: dict[str, float]) -> DecisionOutcome:
        return APPROVED if features[field] < cutoff else BLOCKED

    return predict


def test_the_model_boundary_is_found():
    cf = model_counterfactual(
        field_name="risk_score",
        features={"risk_score": 95},
        predict=approve_below("risk_score", 80),
        current_outcome=BLOCKED,
    )

    assert cf is not None
    assert cf.threshold == 79
    assert cf.direction == "at most"
    assert cf.exact is False, "a searched boundary must not claim to be exact"


def test_no_flip_in_range_reports_nothing():
    """A real and useful answer: the verdict does not hinge on this input."""
    cf = model_counterfactual(
        field_name="risk_score",
        features={"risk_score": 50},
        predict=lambda f: BLOCKED,
        current_outcome=BLOCKED,
    )
    assert cf is None


def test_the_nearest_flip_is_found_not_the_first_in_scan_order():
    """Walking outward in both directions matters: a value 2 below must beat
    one 40 above."""

    def predict(features):
        risk = features["risk_score"]
        return APPROVED if risk in (48, 90) else BLOCKED

    cf = model_counterfactual(
        field_name="risk_score",
        features={"risk_score": 50},
        predict=predict,
        current_outcome=BLOCKED,
    )
    assert cf.threshold == 48


def test_a_non_monotone_model_is_handled_correctly():
    """The reason this scans rather than bisects. A binary search assumes the
    response is ordered; here approval sits in an island the midpoint misses,
    and bisection would report a boundary that does not exist."""

    def predict(features):
        risk = features["risk_score"]
        return APPROVED if 20 <= risk <= 25 else BLOCKED

    cf = model_counterfactual(
        field_name="risk_score",
        features={"risk_score": 95},
        predict=predict,
        current_outcome=BLOCKED,
    )

    assert cf is not None
    assert cf.threshold == 25, "should find the near edge of the island"
    # And the reported value really does flip it — not merely a plausible guess.
    assert predict({"risk_score": cf.threshold}) is APPROVED


def test_the_search_stays_inside_the_field_range():
    """Suggesting a negative risk score, or one above 100, is not advice."""
    low, high, _ = SEARCHABLE_FIELDS["risk_score"]
    probed: list[float] = []

    def predict(features):
        probed.append(features["risk_score"])
        return BLOCKED

    model_counterfactual(
        field_name="risk_score",
        features={"risk_score": 50},
        predict=predict,
        current_outcome=BLOCKED,
    )
    assert probed, "the search should have probed something"
    assert all(low <= value <= high for value in probed)


def test_an_unsearchable_field_is_refused():
    """Telling an operator to change the agent's lifecycle state would be
    telling them to fake a governance state."""
    cf = model_counterfactual(
        field_name="agent_lifecycle",
        features={"agent_lifecycle": 1},
        predict=lambda f: APPROVED,
        current_outcome=BLOCKED,
    )
    assert cf is None


def test_a_missing_feature_is_refused():
    cf = model_counterfactual(
        field_name="amount_usd",
        features={"risk_score": 50},
        predict=lambda f: APPROVED,
        current_outcome=BLOCKED,
    )
    assert cf is None


def test_counterfactuals_are_ranked_by_relative_change():
    """Ranked against each field's own range, so a $500 move does not always
    look bigger than a 5-point one."""

    def predict(features):
        # A small trust change flips it; a large amount change also would.
        if features.get("trust_score", 0) >= 60:
            return APPROVED
        if features.get("amount_usd", 0) <= 100:
            return APPROVED
        return BLOCKED

    cfs = model_counterfactuals(
        features={"trust_score": 55, "amount_usd": 50_000, "risk_score": 40},
        predict=predict,
        current_outcome=BLOCKED,
    )

    assert cfs, "at least one flip should be found"
    assert cfs[0].field == "trust_score", "the proportionally smaller change should rank first"


# --- narrative ---------------------------------------------------------------


def test_the_headline_names_what_decided_it():
    assert "policy rule" in headline(BLOCKED, "policy", "Travel Agent")
    assert "trained model" in headline(ESCALATED, "model", "Travel Agent")


def test_the_headline_reads_as_a_sentence_about_the_outcome():
    assert headline(APPROVED, "model", "Fraud Agent").startswith(
        "Fraud Agent's action was approved"
    )


# --- drivers -----------------------------------------------------------------


def test_drivers_are_ranked_by_absolute_contribution():
    """The largest negative influence explains a refusal as much as the
    largest positive one explains an approval."""
    drivers = drivers_from_attribution({"policy": 0.1, "risk": -0.8, "history": 0.3})

    # |-0.8| > |0.3| > |0.1|
    assert [d.key for d in drivers] == ["risk", "history", "policy"]


def test_driver_signs_are_preserved():
    drivers = drivers_from_attribution({"risk": -0.8})
    assert drivers[0].contribution == pytest.approx(-0.8)


def test_no_attribution_yields_no_drivers():
    """Without a trained model there is nothing to attribute, and inventing
    weights would misrepresent the heuristic fallback as a model."""
    assert drivers_from_attribution(None) == []
