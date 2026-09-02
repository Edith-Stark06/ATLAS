"""Trust endpoint tests against a seeded database.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest


@pytest.fixture
async def _recompute_leaves_no_residue():
    """`/trust/recompute` commits real rows — that persistence is the exact
    thing the two tests using this fixture exist to prove. Left alone, every
    run adds one flat TrustSnapshot per agent per call, permanently, to the
    same dev database every other test run also shares. `load_snapshots`
    only keeps the newest 40 per agent, so enough accumulated flat entries
    eventually crowd the seeded decline out of agt-expense-02's window —
    `test_declining_agent_is_flagged_as_drifting` then starts failing purely
    because the suite has been run enough times, not because anything is
    wrong. Same principle as test_editing_a_stored_entry_breaks_verification
    in test_decision_pipeline.py: prove the behaviour, then leave no trace.
    """
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models import TrustSnapshot

    async with AsyncSessionLocal() as session:
        before_ids = set(
            (
                await session.execute(
                    select(TrustSnapshot.id).where(TrustSnapshot.reason == "recompute")
                )
            ).scalars()
        )

    yield

    async with AsyncSessionLocal() as session:
        new_rows = (
            await session.execute(select(TrustSnapshot).where(TrustSnapshot.reason == "recompute"))
        ).scalars()
        for row in new_rows:
            if row.id not in before_ids:
                await session.delete(row)
        await session.commit()


def test_score_is_reproducible_from_its_source(client):
    """The headline number must be reproducible from its own parts, whichever
    source produced it — the heuristic path (base - penalty) when no trained
    model is loaded, or the ML path (with an attribution) when one is."""
    evaluation = client.get("/api/v1/trust/agents/agt-expense-02").json()

    if evaluation["scoreSource"] == "heuristic":
        expected = round(evaluation["baseScore"] - evaluation["anomalyPenalty"])
        assert evaluation["score"] == expected
    else:
        assert evaluation["scoreSource"] == "ml"
        assert 0 <= evaluation["score"] <= 100
        assert evaluation["mlAttribution"] is not None
        assert set(evaluation["mlAttribution"]) == {
            "behavior",
            "policy",
            "risk",
            "context",
            "history",
        }


def test_ml_model_info_matches_what_agents_report(client):
    """/trust/model-info's availability flag must agree with whether agent
    evaluations actually report scoreSource == "ml"."""
    info = client.get("/api/v1/trust/model-info").json()
    evaluation = client.get("/api/v1/trust/agents/agt-travel-01").json()

    if info["available"]:
        assert evaluation["scoreSource"] == "ml"
        assert info["metrics"]["trust_model"]["learned_auc"] > 0
    else:
        assert evaluation["scoreSource"] == "heuristic"


def test_reloading_models_reports_the_same_state_when_nothing_on_disk_changed(client):
    """POST /reload-models clears the cached loaders and re-reads disk — with
    nothing actually swapped in between, it must report exactly what
    /model-info already did, not something newly stale or newly wrong."""
    before = client.get("/api/v1/trust/model-info").json()
    reloaded = client.post("/api/v1/trust/reload-models").json()

    assert reloaded["available"] == before["available"]
    assert reloaded["trainedAt"] == before["trainedAt"]


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
    """forecast is computed purely from persisted history (trust_engine.
    forecast(snapshots)), independent of the live score — which may itself be
    freshly ML-scored even when history predates the model existing. Compare
    against the history trend, not the single live `score`, so this doesn't
    flake across that transition."""
    evaluation = client.get("/api/v1/trust/agents/agt-expense-02").json()
    history_scores = [h["score"] for h in evaluation["history"]]
    forecast = evaluation["forecast"]

    assert forecast is not None
    assert 0 <= forecast <= 100
    if history_scores[-1] < history_scores[0]:  # this agent's history is declining
        assert forecast <= max(history_scores)


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


def test_recompute_records_a_snapshot_for_every_agent(client, _recompute_leaves_no_residue):
    before = len(client.get("/api/v1/trust/agents/agt-travel-01").json()["history"])

    response = client.post("/api/v1/trust/recompute")
    assert response.status_code == 200

    body = response.json()
    assert body["evaluated"] == len(client.get("/api/v1/agents").json())

    after = len(client.get("/api/v1/trust/agents/agt-travel-01").json()["history"])
    assert after == before + 1


def test_recompute_is_stable_when_nothing_changed(client, _recompute_leaves_no_residue):
    """Two consecutive recomputes over unchanged inputs must agree — the score
    is a function of stored data, not of when it was asked for."""
    first = {
        r["agentId"]: r["score"] for r in client.post("/api/v1/trust/recompute").json()["results"]
    }
    second = {
        r["agentId"]: r["score"] for r in client.post("/api/v1/trust/recompute").json()["results"]
    }

    assert first == second


def test_simulate_returns_a_probability_distribution(client):
    response = client.post(
        "/api/v1/trust/simulate",
        json={
            "trustScore": 71,
            "riskScore": 84,
            "amountUsd": 12450,
            "policyPassRate": 0.2,
            "authorityLevel": 2,
            "hour": 3,
        },
    )
    assert response.status_code == 200

    body = response.json()
    outcomes = {o["outcome"]: o["probability"] for o in body["outcomes"]}
    assert set(outcomes) == {"approved", "escalated", "blocked"}
    assert pytest.approx(sum(outcomes.values()), abs=1e-3) == 1.0
    assert body["recommendation"] in outcomes


def test_simulate_responds_to_its_inputs(client):
    """A low-trust, high-risk, off-hours, large-amount request should not
    score identically to a clean daytime one — otherwise the model is
    ignoring its features, same as the fixed percentages it replaced."""
    risky = client.post(
        "/api/v1/trust/simulate",
        json={
            "trustScore": 20,
            "riskScore": 95,
            "amountUsd": 500_000,
            "policyPassRate": 0.1,
            "authorityLevel": 1,
            "hour": 3,
        },
    ).json()
    clean = client.post(
        "/api/v1/trust/simulate",
        json={
            "trustScore": 95,
            "riskScore": 5,
            "amountUsd": 200,
            "policyPassRate": 0.99,
            "authorityLevel": 4,
            "hour": 14,
        },
    ).json()

    risky_approve = next(o["probability"] for o in risky["outcomes"] if o["outcome"] == "approved")
    clean_approve = next(o["probability"] for o in clean["outcomes"] if o["outcome"] == "approved")
    assert clean_approve > risky_approve
