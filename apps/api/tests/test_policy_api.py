"""Policy Brain endpoint tests against a seeded database.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

LOW_TRUST_HIGH_VALUE = {
    "conditions": [
        {"field": "trust_score", "operator": "lt", "value": 70},
        {"field": "amount_usd", "operator": "gt", "value": 5000},
    ],
    "combinator": "all",
    "effect": "require_human_review",
    "applies_to": [],
}


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        if c.get("/api/v1/health").json()["status"] != "healthy":
            pytest.skip("database unavailable — start it with `npm run db:up`")
        yield c


# --- vocabulary -------------------------------------------------------------


def test_vocabulary_describes_what_the_engine_accepts(client):
    """The authoring UI builds its pickers from this, so it must stay in
    step with the engine rather than being hard-coded client-side."""
    vocab = client.get("/api/v1/policy/vocabulary").json()

    field_keys = {f["key"] for f in vocab["fields"]}
    assert {"trust_score", "risk_score", "amount_usd", "agent_lifecycle"} <= field_keys
    assert {"lt", "gt", "in", "not_in"} <= set(vocab["operators"])
    assert set(vocab["effects"]) == {"allow", "require_human_review", "block"}
    assert set(vocab["combinators"]) == {"all", "any"}


def test_vocabulary_capabilities_come_from_real_agents(client):
    vocab = client.get("/api/v1/policy/vocabulary").json()
    agents = client.get("/api/v1/agents").json()

    assert set(vocab["capabilities"]) == {a["capability"] for a in agents}


# --- reading policies -------------------------------------------------------


def test_policies_carry_their_active_rule(client):
    policies = client.get("/api/v1/policy/policies").json()

    assert policies
    with_rules = [p for p in policies if p["rule"] is not None]
    assert with_rules, "seeded policies should all have an active rule version"

    for policy in with_rules:
        assert policy["rule"]["conditions"]
        assert policy["summary"][0].startswith("IF ")
        assert policy["summary"][1].startswith("THEN ")


def test_policies_list_enabled_first(client):
    enabled = [p["enabled"] for p in client.get("/api/v1/policy/policies").json()]
    assert enabled == sorted(enabled, reverse=True)


def test_policy_detail_includes_version_history(client):
    detail = client.get("/api/v1/policy/policies/pol-14").json()

    assert detail["id"] == "pol-14"
    assert detail["versions"], "seeded policy should have at least its initial version"
    assert detail["versions"][0]["rule"]["conditions"]


def test_unknown_policy_returns_404(client):
    assert client.get("/api/v1/policy/policies/nope").status_code == 404
    assert client.get("/api/v1/policy/policies/nope/versions").status_code == 404


# --- evaluation -------------------------------------------------------------


def test_clean_decision_is_allowed(client):
    """High trust, low risk, small amount — nothing should fire."""
    result = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": 97,
            "riskScore": 5,
            "amountUsd": 120,
            "authorityLevel": 4,
            "agentLifecycle": "trusted",
            "capability": "Risk & Fraud",
            "hourUtc": 14,
        },
    ).json()

    assert result["effect"] == "allow"
    assert result["outcome"] == "approved"


def test_low_trust_high_value_requires_review(client):
    result = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": 55,
            "riskScore": 40,
            "amountUsd": 9000,
            "authorityLevel": 2,
            "agentLifecycle": "review",
            "capability": "Travel & Expense",
            "hourUtc": 14,
        },
    ).json()

    assert result["effect"] in {"require_human_review", "block"}
    triggered = [e for e in result["evaluations"] if e["matched"]]
    assert triggered, "at least one seeded policy should catch this"


def test_extreme_risk_blocks(client):
    """pol-06 (Sanctions Screening) blocks at risk >= 90 for every agent, and
    block must win over any concurrent review effect."""
    result = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": 95,
            "riskScore": 95,
            "amountUsd": 100,
            "authorityLevel": 4,
            "agentLifecycle": "trusted",
            "capability": "Payments",
            "hourUtc": 14,
        },
    ).json()

    assert result["effect"] == "block"
    assert result["outcome"] == "blocked"


def test_evaluation_reports_per_policy_evidence(client):
    result = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": 55,
            "riskScore": 40,
            "amountUsd": 9000,
            "authorityLevel": 2,
            "agentLifecycle": "review",
            "capability": "Travel & Expense",
            "hourUtc": 14,
        },
    ).json()

    assert result["evaluations"], "every evaluated policy should be reported"
    for evaluation in result["evaluations"]:
        assert "policyId" in evaluation
        if evaluation["inScope"]:
            assert evaluation["conditions"], "in-scope policies must show their conditions"


def test_scope_keeps_a_payments_rule_off_a_travel_agent(client):
    """pol-09 caps cross-border settlement for Payments agents only. The same
    amount from a Travel agent must not trigger it."""
    result = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": 95,
            "riskScore": 10,
            "amountUsd": 2_000_000,
            "authorityLevel": 3,
            "agentLifecycle": "trusted",
            "capability": "Travel & Expense",
            "hourUtc": 14,
        },
    ).json()

    by_id = {e["policyId"]: e for e in result["evaluations"]}
    assert by_id["pol-09"]["inScope"] is False
    assert by_id["pol-09"]["matched"] is False


def test_missing_amount_does_not_trigger_an_amount_rule(client):
    """A card freeze has no amount. An amount-threshold policy must not fire
    on it — the condition is unevaluable, not satisfied."""
    result = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": 97,
            "riskScore": 8,
            "amountUsd": None,
            "authorityLevel": 4,
            "agentLifecycle": "trusted",
            "capability": "Risk & Fraud",
            "hourUtc": 14,
        },
    ).json()

    by_id = {e["policyId"]: e for e in result["evaluations"]}
    assert by_id["pol-14"]["matched"] is False
    skipped = [c for c in by_id["pol-14"]["conditions"] if c["skipped"]]
    assert skipped, "the amount condition should be reported as unevaluable"


# --- simulation -------------------------------------------------------------


def test_simulation_replays_the_rule_over_stored_decisions(client):
    result = client.post("/api/v1/policy/simulate", json={"rule": LOW_TRUST_HIGH_VALUE}).json()

    decisions = client.get("/api/v1/decisions").json()
    assert result["evaluated"] == len(decisions)
    assert (
        result["wouldBlock"] + result["wouldEscalate"] + result["wouldAllow"] == result["evaluated"]
    )


def test_simulation_flags_which_outcomes_would_change(client):
    result = client.post("/api/v1/policy/simulate", json={"rule": LOW_TRUST_HIGH_VALUE}).json()

    for changed in result["changed"]:
        assert changed["recordedOutcome"] != changed["simulatedOutcome"]


def test_a_rule_that_matches_nothing_changes_nothing(client):
    impossible = {
        "conditions": [{"field": "trust_score", "operator": "lt", "value": 0}],
        "combinator": "all",
        "effect": "block",
        "applies_to": [],
    }
    result = client.post("/api/v1/policy/simulate", json={"rule": impossible}).json()

    assert result["matched"] == 0
    assert result["wouldBlock"] == 0
    assert result["wouldAllow"] == result["evaluated"]


def test_simulation_rejects_an_invalid_rule(client):
    response = client.post(
        "/api/v1/policy/simulate",
        json={
            "rule": {
                "conditions": [{"field": "nope", "operator": "lt", "value": 1}],
                "effect": "block",
            }
        },
    )
    assert response.status_code == 422
    assert "Unknown field" in response.json()["detail"]


# --- authoring --------------------------------------------------------------


def test_creating_a_version_appends_and_activates(client):
    before = client.get("/api/v1/policy/policies/pol-14").json()
    before_count = len(before["versions"])

    new_rule = {
        "conditions": [
            {"field": "trust_score", "operator": "lt", "value": 65},
            {"field": "amount_usd", "operator": "gt", "value": 7500},
        ],
        "combinator": "all",
        "effect": "require_human_review",
        "applies_to": [],
    }
    created = client.post(
        "/api/v1/policy/policies/pol-14/versions",
        json={"rule": new_rule, "version": "v1.1.0-test", "note": "tightened thresholds"},
    )
    assert created.status_code == 201

    after = client.get("/api/v1/policy/policies/pol-14").json()
    assert len(after["versions"]) == before_count + 1
    assert after["version"] == "v1.1.0-test"
    assert after["rule"]["conditions"][0]["value"] == 65


def test_previous_versions_are_never_mutated(client):
    """The whole point of the version table: an old decision must stay
    explainable against the rule text that actually produced it."""
    detail = client.get("/api/v1/policy/policies/pol-14").json()
    original = [v for v in detail["versions"] if v["createdBy"] == "seed"]
    assert original, "the seeded version should still be on record"
    assert original[0]["rule"]["conditions"][0]["value"] == 70  # the original threshold


def test_creating_a_version_rejects_an_invalid_rule(client):
    response = client.post(
        "/api/v1/policy/policies/pol-14/versions",
        json={
            "rule": {
                "conditions": [{"field": "capability", "operator": "gt", "value": 5}],
                "effect": "block",
            },
            "version": "v9.9.9-bad",
        },
    )
    assert response.status_code == 422


def test_creating_a_version_for_an_unknown_policy_404s(client):
    response = client.post(
        "/api/v1/policy/policies/nope/versions",
        json={"rule": LOW_TRUST_HIGH_VALUE, "version": "v1.0.0"},
    )
    assert response.status_code == 404
