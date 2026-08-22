"""Explain AI endpoint, against a seeded database.

The unit tests cover the counterfactual maths. These cover the thing only the
wired-up system can show: that an explanation is reconstructed from the
*pinned* evidence, and that the counterfactuals it offers are true of the
system that actually made the decision.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest
from fastapi.testclient import TestClient

TRAVEL_AGENT = "agt-travel-01"
FRAUD_AGENT = "agt-fraud-04"


def commit(client: TestClient, **overrides) -> dict:
    payload = {
        "agentId": FRAUD_AGENT,
        "action": "Approve vendor payment",
        "amountUsd": 250,
        "riskScore": 15,
    }
    payload.update(overrides)
    response = client.post("/api/v1/decisions/execute", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def explain(client: TestClient, decision_id: str) -> dict:
    response = client.get(f"/api/v1/explain/decisions/{decision_id}")
    assert response.status_code == 200, response.text
    return response.json()


# --- shape -------------------------------------------------------------------


def test_an_explanation_names_the_outcome_and_what_decided_it(client):
    decision = commit(client)
    result = explain(client, decision["decisionId"])

    assert result["outcome"] == decision["outcome"]
    assert result["decidedBy"] in {"policy", "model"}
    assert result["headline"]
    assert result["agentName"] in result["headline"]


def test_an_explanation_cites_its_audit_record(client):
    decision = commit(client)
    result = explain(client, decision["decisionId"])

    assert result["ledgerSeq"] == decision["ledgerSeq"]
    assert result["fromPinnedEvidence"] is True


def test_an_unknown_decision_is_a_404(client):
    assert client.get("/api/v1/explain/decisions/TRX-NOPE").status_code == 404


def test_explanations_require_credentials(api: TestClient):
    assert api.get("/api/v1/explain/decisions/anything").status_code == 401


# --- rule evidence comes from the pinned record ------------------------------


def test_the_rules_shown_are_the_versions_that_were_in_force(client):
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])
    entry = client.get(f"/api/v1/ledger/{decision['ledgerSeq']}").json()

    pinned = {(r["policyId"], r["version"]) for r in entry["payload"]["policy"]["evaluated"]}
    explained = {(r["policyId"], r["version"]) for r in result["rules"]}

    assert explained == pinned


def test_a_policy_forced_decision_says_so(client):
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])

    assert decision["outcome"] == "blocked"
    assert result["decidedBy"] == "policy"
    assert any("Binding rule" in line for line in result["narrative"])


# --- counterfactuals ---------------------------------------------------------


def test_a_blocked_decision_offers_a_way_to_change_it(client):
    """An explanation that only says "no" is not actionable."""
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])

    assert result["counterfactuals"], "a policy-blocked decision should have a boundary"
    for cf in result["counterfactuals"]:
        assert cf["direction"] in {"at most", "at least"}
        assert cf["detail"]


def test_policy_counterfactuals_are_marked_exact(client):
    """A rule boundary is arithmetic. A model boundary is a probe. Conflating
    them would overstate what the system knows."""
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])

    policy_cfs = [c for c in result["counterfactuals"] if c["source"] == "policy"]
    assert policy_cfs, "the binding rule should yield an exact boundary"
    assert all(c["exact"] is True for c in policy_cfs)


def test_a_policy_counterfactual_actually_stops_the_rule_matching(client):
    """The claim is checkable, so check it: re-evaluate the policy set at the
    suggested value and confirm the restriction lifts."""
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])

    risk_cf = next((c for c in result["counterfactuals"] if c["field"] == "risk_score"), None)
    if risk_cf is None:
        pytest.skip("no risk-score boundary in this decision's binding rules")

    agent = client.get(f"/api/v1/agents/{TRAVEL_AGENT}").json()
    before = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": agent["trustScore"],
            "riskScore": int(risk_cf["current"]),
            "amountUsd": 4820,
            "authorityLevel": 2,
            "agentLifecycle": agent["lifecycle"],
            "capability": agent["capability"],
            "hourUtc": 12,
        },
    ).json()
    after = client.post(
        "/api/v1/policy/evaluate",
        json={
            "trustScore": agent["trustScore"],
            "riskScore": int(risk_cf["threshold"]),
            "amountUsd": 4820,
            "authorityLevel": 2,
            "agentLifecycle": agent["lifecycle"],
            "capability": agent["capability"],
            "hourUtc": 12,
        },
    ).json()

    assert before["effect"] == "block"
    assert after["effect"] != "block", (
        f"risk {risk_cf['threshold']} was supposed to clear the block, got {after['effect']}"
    )


def test_a_counterfactual_is_only_offered_if_it_changes_the_verdict(client):
    """The case that motivated verifying these against the whole rule set.

    A boundary is computed per rule, but the verdict comes from all of them.
    With two rules binding, clearing one leaves the other in force — so a
    change can be exactly right about its own rule and useless as advice. Each
    suggestion is replayed against every rule before being offered.
    """
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])
    agent = client.get(f"/api/v1/agents/{TRAVEL_AGENT}").json()

    for cf in result["counterfactuals"]:
        if cf["source"] != "policy":
            continue

        replayed = client.post(
            "/api/v1/policy/evaluate",
            json={
                "trustScore": agent["trustScore"],
                "riskScore": 95,
                "amountUsd": 4820,
                "authorityLevel": 2,
                "agentLifecycle": agent["lifecycle"],
                "capability": agent["capability"],
                "hourUtc": 12,
                # Override just the field this counterfactual proposes.
                **{
                    {
                        "risk_score": "riskScore",
                        "amount_usd": "amountUsd",
                        "trust_score": "trustScore",
                    }[cf["field"]]: cf["threshold"]
                },
            },
        ).json()

        assert replayed["outcome"] != decision["outcome"], (
            f"{cf['field']} → {cf['threshold']} was offered but leaves the "
            f"outcome at {replayed['outcome']}"
        )
        assert replayed["outcome"] == cf["changesTo"], (
            "the reported new outcome must be what actually happens"
        )


def test_an_approved_decision_needs_no_counterfactual(client):
    """Nothing to change about an outcome the caller wanted."""
    decision = commit(client, amountUsd=40, riskScore=5)
    result = explain(client, decision["decisionId"])

    assert decision["outcome"] == "approved"
    assert result["counterfactuals"] == []


def test_suggested_values_stay_inside_the_field_range(client):
    decision = commit(client, agentId=TRAVEL_AGENT, amountUsd=4820, riskScore=95)
    result = explain(client, decision["decisionId"])

    for cf in result["counterfactuals"]:
        if cf["field"] in {"risk_score", "trust_score"}:
            assert 0 <= cf["threshold"] <= 100, cf


# --- drivers -----------------------------------------------------------------


def test_drivers_are_ranked_and_labelled(client):
    decision = commit(client)
    result = explain(client, decision["decisionId"])

    if not result["drivers"]:
        pytest.skip("no trained trust model loaded")

    magnitudes = [abs(d["contribution"]) for d in result["drivers"]]
    assert magnitudes == sorted(magnitudes, reverse=True)
    assert all(d["label"] for d in result["drivers"])


def test_drivers_are_flagged_as_current_not_historical(client):
    """Per-factor attribution is not snapshotted, so presenting today's
    numbers as the attribution at decision time would be a quiet lie."""
    decision = commit(client)
    result = explain(client, decision["decisionId"])

    assert result["driversAreCurrent"] is True
