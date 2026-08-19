"""Trust endpoint tests against a seeded database.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        if c.get("/api/v1/health").json()["status"] != "healthy":
            pytest.skip("database unavailable — start it with `npm run db:up`")
        yield c


def test_score_equals_base_minus_penalty(client):
    """The headline number must be reproducible from its own parts."""
    evaluation = client.get("/api/v1/trust/agents/agt-expense-02").json()

    expected = round(evaluation["baseScore"] - evaluation["anomalyPenalty"])
    assert evaluation["score"] == expected


def test_adverse_decisions_produce_a_penalty(client):
    """The Expense agent has one blocked and one escalated decision seeded."""
    evaluation = client.get("/api/v1/trust/agents/agt-expense-02").json()
    assert evaluation["anomalyPenalty"] > 0


def test_clean_agent_has_no_penalty(client):
    """The Fraud agent's only seeded decision was approved."""
    evaluation = client.get("/api/v1/trust/agents/agt-fraud-04").json()
    assert evaluation["anomalyPenalty"] == 0


def test_evaluation_explains_itself(client):
    explanation = client.get("/api/v1/trust/agents/agt-expense-02").json()["explanation"]

    assert len(explanation) >= 3
    joined = " ".join(explanation).lower()
    assert "factor mean" in joined
    assert "lifecycle" in joined


def test_declining_agent_is_flagged_as_drifting(client):
    """Seeded history walks the Expense agent down from 94, so drift must fire."""
    drift = client.get("/api/v1/trust/agents/agt-expense-02").json()["drift"]

    assert drift["detected"] is True
    assert drift["delta"] < 0
    assert drift["baseline"] is not None


def test_history_is_returned_oldest_first(client):
    history = client.get("/api/v1/trust/agents/agt-travel-01").json()["history"]

    assert len(history) > 1
    captured = [h["capturedAt"] for h in history]
    assert captured == sorted(captured)


def test_forecast_follows_the_direction_of_travel(client):
    evaluation = client.get("/api/v1/trust/agents/agt-expense-02").json()
    forecast = evaluation["forecast"]

    assert forecast is not None
    # This agent is declining, so the projection should not exceed today.
    assert forecast <= evaluation["score"]


def test_unknown_agent_returns_404(client):
    assert client.get("/api/v1/trust/agents/nope").status_code == 404


def test_overview_counts_every_agent(client):
    overview = client.get("/api/v1/trust/overview").json()
    agents = client.get("/api/v1/agents").json()

    assert overview["agentsEvaluated"] == len(agents)
    assert sum(b["count"] for b in overview["bands"]) == len(agents)


def test_watchlist_is_ordered_worst_drift_first(client):
    watchlist = client.get("/api/v1/trust/overview").json()["watchlist"]

    deltas = [w["drift"]["delta"] for w in watchlist]
    assert deltas == sorted(deltas)


def test_recompute_records_a_snapshot_for_every_agent(client):
    before = len(client.get("/api/v1/trust/agents/agt-travel-01").json()["history"])

    response = client.post("/api/v1/trust/recompute")
    assert response.status_code == 200

    body = response.json()
    assert body["evaluated"] == len(client.get("/api/v1/agents").json())

    after = len(client.get("/api/v1/trust/agents/agt-travel-01").json()["history"])
    assert after == before + 1


def test_recompute_is_stable_when_nothing_changed(client):
    """Two consecutive recomputes over unchanged inputs must agree — the score
    is a function of stored data, not of when it was asked for."""
    first = {
        r["agentId"]: r["score"] for r in client.post("/api/v1/trust/recompute").json()["results"]
    }
    second = {
        r["agentId"]: r["score"] for r in client.post("/api/v1/trust/recompute").json()["results"]
    }

    assert first == second
