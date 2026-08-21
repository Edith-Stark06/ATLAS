"""Unit tests for the Policy Brain's rule engine.

Pure functions over plain values — no database, no trained artifacts.
"""

from datetime import UTC, datetime

import pytest

from app.services.policy_engine import (
    Combinator,
    Condition,
    Effect,
    Operator,
    PolicyContext,
    Rule,
    RuleValidationError,
    combine,
    context_from_decision,
    evaluate_condition,
    evaluate_rule,
    parse_condition,
    parse_rule,
    rule_to_dict,
)


def ctx(**overrides) -> PolicyContext:
    base = {
        "trust_score": 90,
        "risk_score": 10,
        "amount_usd": 1000.0,
        "authority_level": 3,
        "agent_lifecycle": "trusted",
        "capability": "Payments",
        "hour_utc": 14,
    }
    return PolicyContext(**{**base, **overrides})


# --- conditions -------------------------------------------------------------


@pytest.mark.parametrize(
    ("operator", "value", "actual", "expected"),
    [
        (Operator.LT, 70, 60, True),
        (Operator.LT, 70, 70, False),
        (Operator.LTE, 70, 70, True),
        (Operator.GT, 5000, 6000, True),
        (Operator.GT, 5000, 5000, False),
        (Operator.GTE, 5000, 5000, True),
        (Operator.EQ, 50, 50, True),
        (Operator.NEQ, 50, 51, True),
    ],
)
def test_numeric_operators(operator, value, actual, expected):
    condition = Condition(field="trust_score", operator=operator, value=value)
    assert evaluate_condition(condition, ctx(trust_score=actual)).matched is expected


def test_membership_operators():
    in_cond = Condition(field="agent_lifecycle", operator=Operator.IN, value=["anomaly", "review"])
    assert evaluate_condition(in_cond, ctx(agent_lifecycle="review")).matched is True
    assert evaluate_condition(in_cond, ctx(agent_lifecycle="trusted")).matched is False

    not_in = Condition(field="capability", operator=Operator.NOT_IN, value=["Payments"])
    assert evaluate_condition(not_in, ctx(capability="Payments")).matched is False
    assert evaluate_condition(not_in, ctx(capability="Travel")).matched is True


def test_missing_value_is_skipped_not_silently_false():
    """A card freeze has no amount. "We could not tell" must be recorded
    distinctly from "we checked and it was under the limit" — an audit trail
    that conflates them is misleading."""
    condition = Condition(field="amount_usd", operator=Operator.GT, value=5000)
    result = evaluate_condition(condition, ctx(amount_usd=None))

    assert result.matched is False
    assert result.skipped_reason is not None
    assert "not set" in result.skipped_reason
    assert "not evaluated" in result.describe()


def test_type_mismatch_does_not_raise():
    """A rule comparing a string field numerically must fail closed and
    explain itself, not take down the evaluation."""
    condition = Condition(field="capability", operator=Operator.GT, value=5)
    result = evaluate_condition(condition, ctx())

    assert result.matched is False
    assert result.skipped_reason is not None


# --- rules ------------------------------------------------------------------


def all_rule(*conditions, effect=Effect.REQUIRE_HUMAN_REVIEW, applies_to=None) -> Rule:
    return Rule(
        conditions=list(conditions),
        combinator=Combinator.ALL,
        effect=effect,
        applies_to=applies_to or [],
    )


def test_all_combinator_needs_every_condition():
    rule = all_rule(
        Condition("trust_score", Operator.LT, 70),
        Condition("amount_usd", Operator.GT, 5000),
    )

    both = evaluate_rule(rule, ctx(trust_score=60, amount_usd=9000))
    assert both.matched is True
    assert both.effect is Effect.REQUIRE_HUMAN_REVIEW

    only_one = evaluate_rule(rule, ctx(trust_score=60, amount_usd=100))
    assert only_one.matched is False
    assert only_one.effect is None


def test_any_combinator_needs_one_condition():
    rule = Rule(
        conditions=[
            Condition("trust_score", Operator.LT, 70),
            Condition("risk_score", Operator.GT, 80),
        ],
        combinator=Combinator.ANY,
        effect=Effect.BLOCK,
    )

    assert evaluate_rule(rule, ctx(trust_score=60, risk_score=10)).matched is True
    assert evaluate_rule(rule, ctx(trust_score=95, risk_score=90)).matched is True
    assert evaluate_rule(rule, ctx(trust_score=95, risk_score=10)).matched is False


def test_scope_excludes_agents_outside_applies_to():
    rule = all_rule(Condition("trust_score", Operator.LT, 100), applies_to=["Payments"])

    in_scope = evaluate_rule(rule, ctx(capability="Payments"))
    assert in_scope.in_scope is True
    assert in_scope.matched is True

    out = evaluate_rule(rule, ctx(capability="Travel & Expense"))
    assert out.in_scope is False
    assert out.matched is False
    assert out.results == []  # nothing evaluated at all


def test_empty_applies_to_means_every_agent():
    rule = all_rule(Condition("trust_score", Operator.LT, 100), applies_to=[])
    assert evaluate_rule(rule, ctx(capability="Anything")).in_scope is True


def test_evaluation_explains_each_condition():
    rule = all_rule(
        Condition("trust_score", Operator.LT, 70),
        Condition("amount_usd", Operator.GT, 5000),
    )
    evaluation = evaluate_rule(rule, ctx(trust_score=60, amount_usd=9000))

    joined = " ".join(evaluation.explanation)
    assert "Trust Score < 70" in joined
    assert "Amount (USD) > 5000" in joined
    assert "matched" in joined


# --- parsing / validation ---------------------------------------------------


def test_parse_rejects_unknown_field():
    with pytest.raises(RuleValidationError, match="Unknown field"):
        parse_condition({"field": "secret_backdoor", "operator": "lt", "value": 1})


def test_parse_rejects_ordering_a_text_field():
    with pytest.raises(RuleValidationError, match="cannot order a text field"):
        parse_condition({"field": "capability", "operator": "gt", "value": 5})


def test_parse_rejects_non_numeric_operand_for_ordering():
    with pytest.raises(RuleValidationError, match="needs a number"):
        parse_condition({"field": "trust_score", "operator": "lt", "value": "seventy"})


def test_parse_rejects_scalar_for_membership_operator():
    with pytest.raises(RuleValidationError, match="needs a list"):
        parse_condition({"field": "agent_lifecycle", "operator": "in", "value": "review"})


def test_parse_rejects_rule_with_no_conditions():
    with pytest.raises(RuleValidationError, match="at least one condition"):
        parse_rule({"conditions": [], "effect": "block"})


def test_parse_rejects_unknown_effect():
    with pytest.raises(RuleValidationError):
        parse_rule(
            {
                "conditions": [{"field": "trust_score", "operator": "lt", "value": 70}],
                "effect": "delete_everything",
            }
        )


def test_rule_survives_a_dict_round_trip():
    original = {
        "conditions": [
            {"field": "trust_score", "operator": "lt", "value": 70},
            {"field": "amount_usd", "operator": "gt", "value": 5000},
        ],
        "combinator": "all",
        "effect": "require_human_review",
        "applies_to": ["Payments"],
    }
    assert rule_to_dict(parse_rule(original)) == original


def test_combinator_defaults_to_all():
    rule = parse_rule(
        {"conditions": [{"field": "trust_score", "operator": "lt", "value": 70}], "effect": "block"}
    )
    assert rule.combinator is Combinator.ALL


# --- combining several policies ---------------------------------------------


def _eval(policy_id, name, rule, context):
    return (policy_id, name, rule, evaluate_rule(rule, context))


def test_no_matching_policy_allows():
    """Policies restrict an otherwise-permitted action. An empty or
    non-matching policy set must not halt the estate."""
    rule = all_rule(Condition("trust_score", Operator.LT, 10))
    decision = combine([_eval("pol-1", "Low Trust", rule, ctx(trust_score=95))])

    assert decision.effect is Effect.ALLOW
    assert decision.triggered == []
    assert len(decision.passed) == 1


def test_empty_policy_set_allows():
    assert combine([]).effect is Effect.ALLOW


def test_most_restrictive_effect_wins():
    review = all_rule(Condition("trust_score", Operator.LT, 95), effect=Effect.REQUIRE_HUMAN_REVIEW)
    block = all_rule(Condition("risk_score", Operator.GT, 5), effect=Effect.BLOCK)
    allow = all_rule(Condition("authority_level", Operator.GTE, 1), effect=Effect.ALLOW)

    context = ctx(trust_score=90, risk_score=50, authority_level=3)
    decision = combine(
        [
            _eval("pol-a", "Review", review, context),
            _eval("pol-b", "Block", block, context),
            _eval("pol-c", "Allow", allow, context),
        ]
    )

    assert decision.effect is Effect.BLOCK
    assert decision.triggered[0][2] is Effect.BLOCK  # most restrictive sorted first
    assert len(decision.triggered) == 3


def test_allow_rule_cannot_override_a_block():
    block = all_rule(Condition("risk_score", Operator.GT, 5), effect=Effect.BLOCK)
    allow = all_rule(Condition("trust_score", Operator.GT, 5), effect=Effect.ALLOW)

    context = ctx(risk_score=50, trust_score=90)
    decision = combine(
        [_eval("pol-a", "Allow", allow, context), _eval("pol-b", "Block", block, context)]
    )
    assert decision.effect is Effect.BLOCK


def test_out_of_scope_policies_are_reported_separately():
    rule = all_rule(Condition("trust_score", Operator.LT, 100), applies_to=["Payments"])
    decision = combine([_eval("pol-1", "Payments only", rule, ctx(capability="Travel"))])

    assert decision.effect is Effect.ALLOW
    assert decision.out_of_scope == [("pol-1", "Payments only")]
    assert decision.passed == []


def test_decision_explains_which_policy_fired():
    rule = all_rule(Condition("trust_score", Operator.LT, 95), effect=Effect.BLOCK)
    decision = combine([_eval("pol-9", "Cross-Border Cap", rule, ctx(trust_score=60))])

    joined = " ".join(decision.explanation)
    assert "Cross-Border Cap" in joined
    assert "pol-9" in joined
    assert "block" in joined


# --- context construction ---------------------------------------------------


def test_context_extracts_hour_from_the_decision_timestamp():
    context = context_from_decision(
        trust_score=71,
        risk_score=84,
        amount_usd=12450.0,
        authority_level=2,
        agent_lifecycle="review",
        capability="Travel & Expense",
        decided_at=datetime(2026, 8, 19, 3, 14, tzinfo=UTC),
    )
    assert context.hour_utc == 3
    assert context.amount_usd == 12450.0
