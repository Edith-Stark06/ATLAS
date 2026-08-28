"""Vertical packs: domain vocabulary, scoping, and isolation.

The risk with a plugin vocabulary is not that it fails loudly — it is that a
rule quietly means something it should not. These concentrate on that: a funds
rule firing on a travel decision, a pack shadowing a core field, two packs
claiming one name, and a domain value being read as zero rather than absent.
"""

import pytest

from app import domains
from app.services import policy_engine
from app.services.policy_engine import (
    CORE_FIELDS,
    Effect,
    PolicyContext,
    evaluable_fields,
    evaluate_rule,
    parse_rule,
)


def context(capability: str = "Mutual Funds", **attributes) -> PolicyContext:
    return PolicyContext(
        trust_score=85,
        risk_score=20,
        amount_usd=1000.0,
        authority_level=2,
        agent_lifecycle="healthy",
        capability=capability,
        hour_utc=12,
        attributes=attributes,
    )


# --- the registry ------------------------------------------------------------


def test_every_pack_declares_what_it_governs():
    for pack in domains.all_packs():
        assert pack.key
        assert pack.capabilities, f"{pack.key} governs nothing"
        assert pack.fields, f"{pack.key} contributes no vocabulary"


def test_field_names_are_unique_across_packs():
    """Two packs declaring `risk_tier` with different meanings would make a
    rule's behaviour depend on which pack imported first."""
    seen: dict[str, str] = {}
    for pack in domains.all_packs():
        for name in pack.fields:
            assert name not in seen, f"'{name}' declared by both {seen.get(name)} and {pack.key}"
            seen[name] = pack.key


def test_a_pack_cannot_shadow_a_core_field():
    """Core wins a name clash, so a pack redefining `risk_score` would change
    what every existing rule means without touching any of them."""
    for pack in domains.all_packs():
        assert not (set(pack.fields) & set(CORE_FIELDS)), (
            f"{pack.key} redefines a core field"
        )


def test_the_vocabulary_is_core_plus_every_pack():
    resolved = evaluable_fields()

    assert set(CORE_FIELDS) <= set(resolved)
    for pack in domains.all_packs():
        assert set(pack.fields) <= set(resolved), f"{pack.key} fields missing"


def test_a_field_reports_which_pack_declares_it():
    assert domains.pack_for_field("portfolio_concentration_pct").key == "investments"
    assert domains.pack_for_field("destination_risk_tier").key == "travel"
    assert domains.pack_for_field("overbooking").key == "booking"


def test_a_core_field_belongs_to_no_pack():
    """The authoring UI groups by domain; a core field must not be filed
    under an arbitrary one."""
    assert domains.pack_for_field("risk_score") is None


def test_a_capability_no_pack_claims_is_governed_by_core_alone():
    """That is the correct default, not a gap — most agents need no vertical
    vocabulary at all."""
    assert domains.pack_for_capability("Risk & Fraud") is None
    assert domains.pack_for_capability("Mutual Funds").key == "investments"


# --- domain values are readable, and absent means absent ---------------------


def test_a_domain_field_is_readable_from_the_context():
    ctx = context(portfolio_concentration_pct=31.0)
    assert ctx.get("portfolio_concentration_pct") == 31.0


def test_a_core_field_still_resolves_normally():
    assert context().get("risk_score") == 20


def test_core_wins_a_name_clash_with_an_attribute():
    """Belt and braces on top of the no-shadowing rule: even if an attribute
    dict carried `risk_score`, the real one must win."""
    ctx = context(risk_score=999)
    assert ctx.get("risk_score") == 20


def test_an_absent_domain_value_is_none_not_zero():
    """The whole isolation property. Zero would make `concentration > 25`
    evaluate cleanly to False, which is a different claim from "this decision
    carries no concentration at all"."""
    assert context().get("portfolio_concentration_pct") is None


# --- a rule from one domain must not fire on another -------------------------


def concentration_rule():
    return parse_rule(
        {
            "conditions": [
                {"field": "portfolio_concentration_pct", "operator": "gt", "value": 25}
            ],
            "combinator": "all",
            "effect": "block",
            "applies_to": ["Mutual Funds"],
        }
    )


def test_a_domain_rule_fires_on_its_own_domain():
    result = evaluate_rule(
        concentration_rule(), context("Mutual Funds", portfolio_concentration_pct=31.0)
    )

    assert result.in_scope is True
    assert result.matched is True
    assert result.effect is Effect.BLOCK


def test_a_domain_rule_does_not_fire_when_its_field_is_absent():
    """A travel decision carries no concentration. The condition is
    unevaluable, so the rule declines rather than blocking something it knows
    nothing about."""
    result = evaluate_rule(
        concentration_rule(), context("Mutual Funds", destination_risk_tier="high")
    )

    assert result.matched is False
    skipped = [c for c in result.results if c.skipped_reason]
    assert skipped, "the missing field should be reported as unevaluable"


def test_scope_keeps_a_funds_rule_off_a_travel_agent():
    """Two independent guards — scope and the absent field. Either alone
    would do; both is deliberate."""
    result = evaluate_rule(
        concentration_rule(), context("Travel Safety", portfolio_concentration_pct=31.0)
    )

    assert result.in_scope is False
    assert result.matched is False


# --- shipped rules are ordinary rules ----------------------------------------


def test_every_shipped_rule_parses():
    """A pack's rules go through the same parser as anything an operator
    writes. A typo in a shipped rule should fail here, not in production."""
    for pack in domains.all_packs():
        for rule in pack.policies:
            parse_rule(rule.rule)


def test_every_shipped_rule_only_uses_fields_that_exist():
    resolved = evaluable_fields()
    for pack in domains.all_packs():
        for rule in pack.policies:
            for condition in rule.rule["conditions"]:
                assert condition["field"] in resolved, (
                    f"{rule.policy_id} references unknown field {condition['field']}"
                )


def test_a_shipped_rule_only_uses_core_or_its_own_domains_fields():
    """A booking rule reaching for a funds field would be a rule that can
    never fire — valid, parseable, and silently dead."""
    for pack in domains.all_packs():
        allowed = set(CORE_FIELDS) | set(pack.fields)
        for rule in pack.policies:
            for condition in rule.rule["conditions"]:
                assert condition["field"] in allowed, (
                    f"{rule.policy_id} in pack '{pack.key}' uses "
                    f"'{condition['field']}', which belongs to another domain"
                )


def test_a_shipped_rule_is_scoped_to_its_packs_capabilities():
    for pack in domains.all_packs():
        for rule in pack.policies:
            applies = set(rule.rule.get("applies_to") or [])
            assert applies, f"{rule.policy_id} applies to everything"
            assert applies <= set(pack.capabilities), (
                f"{rule.policy_id} claims capabilities its pack does not govern"
            )


# --- unknown fields are still rejected ---------------------------------------


def test_an_unknown_field_is_still_refused():
    """Extending the vocabulary must not open it."""
    with pytest.raises(policy_engine.RuleValidationError):
        parse_rule(
            {
                "conditions": [{"field": "not_a_real_field", "operator": "gt", "value": 1}],
                "combinator": "all",
                "effect": "block",
                "applies_to": [],
            }
        )
