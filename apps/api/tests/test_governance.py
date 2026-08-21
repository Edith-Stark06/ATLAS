"""Endpoint tests against a seeded database.

These are integration tests: they need Postgres up (`npm run db:up`) and seeded
(`python -m app.seed --reset`). When the database is unreachable the whole
module skips rather than failing, so `pytest` stays meaningful on a machine
with no Docker running.
"""


def test_agents_are_listed_by_descending_trust(client):
    agents = client.get("/api/v1/agents").json()

    assert len(agents) > 0
    scores = [a["trustScore"] for a in agents]
    assert scores == sorted(scores, reverse=True)


def test_agent_payload_uses_camel_case(client):
    agent = client.get("/api/v1/agents").json()[0]

    # The TypeScript client consumes these names directly.
    for key in ("trustScore", "trustDelta", "decisionsToday", "lastActiveAt", "authorityLevel"):
        assert key in agent, f"missing {key}"
    assert isinstance(agent["factors"], list) and agent["factors"]


def test_unknown_agent_returns_404(client):
    assert client.get("/api/v1/agents/does-not-exist").status_code == 404


def test_decision_includes_policy_evidence_and_agent_name(client):
    decision = client.get("/api/v1/decisions/EXP-8892-BL").json()

    assert decision["outcome"] == "blocked"
    assert decision["agentName"] == "Expense Approval Agent"
    # Money must survive as a number, not a string.
    assert decision["amountUsd"] == 12450.0
    assert len(decision["policyChecks"]) == 4
    assert sum(1 for c in decision["policyChecks"] if not c["passed"]) == 3


def test_blocked_decision_carries_investigation(client):
    investigation = client.get("/api/v1/decisions/EXP-8892-BL").json()["investigation"]

    assert investigation is not None
    assert investigation["trustBefore"] == 94
    assert investigation["riskVector"]["financial"] == 90
    assert len(investigation["criticalFactors"]) == 2


def test_approved_decision_has_no_investigation(client):
    assert client.get("/api/v1/decisions/TRX-9871").json()["investigation"] is None


def test_unknown_decision_returns_404(client):
    assert client.get("/api/v1/decisions/NOPE-1").status_code == 404


def test_decisions_are_newest_first(client):
    decided = [d["decidedAt"] for d in client.get("/api/v1/decisions").json()]
    assert decided == sorted(decided, reverse=True)


def test_simulation_outcome_probabilities_are_fractions(client):
    runs = client.get("/api/v1/simulations").json()

    assert runs
    for run in runs:
        assert run["outcomes"], f"{run['id']} has no outcomes"
        for outcome in run["outcomes"]:
            assert 0.0 <= outcome["probability"] <= 1.0


def test_dashboard_aggregates_from_stored_rows(client):
    dashboard = client.get("/api/v1/dashboard").json()
    agents = client.get("/api/v1/agents").json()

    metrics = {m["key"]: m["value"] for m in dashboard["metrics"]}
    assert metrics["agents"] == str(len(agents))

    expected_avg = round(sum(a["trustScore"] for a in agents) / len(agents))
    assert dashboard["compositeTrust"]["score"] == expected_avg


def test_dashboard_forecast_is_grounded_in_stored_history(client):
    """The forecast is projected from the estate trend, which is the average
    trust per evaluation round. It is null only when history is too short —
    never an extrapolation of unrelated numbers."""
    composite = client.get("/api/v1/dashboard").json()["compositeTrust"]
    trend = composite["trend"]
    predicted = composite["predicted"]

    if len(trend) < 3:
        assert predicted is None
    else:
        assert predicted is not None
        # A projection one step beyond the series should stay in range and
        # near it — not wander off to an implausible value.
        assert 0 <= predicted <= 100
        assert min(trend) - 15 <= predicted <= max(trend) + 15


def test_live_pipeline_reflects_the_latest_decision(client):
    dashboard = client.get("/api/v1/dashboard").json()
    latest = client.get("/api/v1/decisions").json()[0]

    pipeline = dashboard["livePipeline"]
    assert pipeline["transactionId"] == latest["id"]
    assert [s["key"] for s in pipeline["stages"]][:3] == ["request", "trust", "policy"]


def test_policies_list_enabled_first(client):
    policies = client.get("/api/v1/policies").json()

    assert policies
    enabled_flags = [p["enabled"] for p in policies]
    assert enabled_flags == sorted(enabled_flags, reverse=True)
