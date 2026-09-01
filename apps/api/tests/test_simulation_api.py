"""Simulation Engine endpoint tests against a seeded database.

The unit tests in test_simulation_engine.py cover the maths on plain values.
These cover what only the wired-up system can show: that the trained model,
the stored policy versions and the agent's live trust actually reach the
verdict, and that a what-if leaves no trace behind.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest

#: Seeded agent with a travel capability — the sanctions rule blocks its
#: high-risk actions, which is what makes the policy override observable.
TRAVEL_AGENT = "agt-travel-01"


def run(client, **overrides):
    payload = {
        "action": "Book flight LHR to JFK",
        "agentId": TRAVEL_AGENT,
        "amountUsd": 4820,
        "riskScore": 95,
    }
    payload.update(overrides)
    response = client.post("/api/v1/simulation/run", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- the pipeline is really wired up -----------------------------------------


def test_the_agents_stored_trust_is_used_when_none_is_given(client):
    agent = client.get(f"/api/v1/agents/{TRAVEL_AGENT}").json()
    result = run(client)

    assert result["trustScore"] == agent["trustScore"]
    assert result["agentName"] == agent["name"]


def test_a_trust_override_answers_the_what_if(client):
    """The whole point of the workspace: ask what happens at a trust score
    the agent does not currently have."""
    result = run(client, trustScore=40)

    assert result["trustScore"] == 40


def test_every_enabled_policy_is_evaluated(client):
    policies = client.get("/api/v1/policy/policies").json()
    enabled = {p["id"] for p in policies if p["enabled"]}
    result = run(client)

    assert {entry["policyId"] for entry in result["policyTrace"]} == enabled
    # Every entry names the version it evaluated, so a verdict can be replayed
    # against the exact rule text that produced it.
    assert all(entry["version"] for entry in result["policyTrace"])


def test_a_disabled_policy_does_not_govern(client):
    """A disabled rule must not quietly influence a verdict — and must not
    appear in the trace claiming it was considered."""
    policies = client.get("/api/v1/policy/policies").json()
    disabled = {p["id"] for p in policies if not p["enabled"]}
    if not disabled:
        pytest.skip("no disabled policy in the seeded set")

    traced = {entry["policyId"] for entry in run(client)["policyTrace"]}
    assert traced.isdisjoint(disabled)


def test_predictions_come_from_the_trained_model(client):
    result = run(client)

    assert result["modelBacked"] is True
    probabilities = [o["probability"] for o in result["outcomes"]]
    assert sum(probabilities) == pytest.approx(1.0, abs=1e-3)
    # An even split would mean the fallback ran, not the classifier.
    assert len(set(probabilities)) > 1


# --- policy beats the model, end to end --------------------------------------


def test_a_blocking_rule_overrides_a_confident_model(client):
    result = run(client)

    assert result["policyEffect"] == "block"
    assert result["policyForced"] is True
    assert result["recommendation"] == "blocked"

    approved = next(o for o in result["outcomes"] if o["outcome"] == "approved")
    assert approved["probability"] > 0.5, "the model does favour approving this"
    assert approved["compliant"] is False


def test_a_blocked_action_moves_no_money(client):
    result = run(client)

    assert result["expectedExposureUsd"] == 0
    assert result["withheldUsd"] == pytest.approx(4820)
    # Still reported, so the value of the block is visible rather than implied.
    assert result["unconstrainedExposureUsd"] > 0


def test_a_low_risk_action_is_allowed_through(client):
    """Governance that blocks everything is not governance — the permissive
    path has to work too."""
    result = run(client, amountUsd=40, riskScore=5, trustScore=95)

    assert result["recommendation"] == "approved"
    assert result["policyForced"] is False
    assert result["expectedExposureUsd"] == pytest.approx(40)
    assert result["withheldUsd"] == 0


# --- what-ifs stay out of the audit trail ------------------------------------


def test_running_a_simulation_records_nothing(client):
    before = client.get("/api/v1/simulations").json()
    run(client)
    after = client.get("/api/v1/simulations").json()

    assert [s["id"] for s in after] == [s["id"] for s in before]


def test_a_simulation_is_not_logged_as_a_decision(client):
    before = client.get("/api/v1/decisions").json()
    run(client, action="Wire transfer to unverified beneficiary")
    after = client.get("/api/v1/decisions").json()

    assert len(after) == len(before)


# --- validation --------------------------------------------------------------


def test_an_unknown_agent_is_rejected(client):
    response = client.post(
        "/api/v1/simulation/run",
        json={"action": "x", "agentId": "agt-does-not-exist", "riskScore": 10},
    )
    assert response.status_code == 404


def test_an_out_of_range_risk_score_is_rejected(client):
    response = client.post(
        "/api/v1/simulation/run",
        json={"action": "x", "agentId": TRAVEL_AGENT, "riskScore": 140},
    )
    assert response.status_code == 422


def test_an_action_without_an_agent_still_gets_a_verdict(client):
    """Not every proposal comes from a registered agent — an unattributed
    request must still be governed rather than erroring out."""
    result = run(client, agentId=None)

    assert result["recommendation"] in {"approved", "escalated", "blocked"}
    assert result["policyTrace"]


# --- rebuild -----------------------------------------------------------------


async def test_rebuild_covers_every_decision(client):
    """Rebuild is keyed on decisions, not on whatever runs happen to exist —
    a seed that shipped simulations for only some decisions ends up with a
    prediction attached to all of them.

    Asserted as containment rather than an exact count: `/decisions` is
    paginated, so comparing its length to a full rebuild would silently start
    failing once the pipeline has written more than one page of decisions.

    The containment check reads `SimulationRun` directly rather than through
    `GET /simulations` — that endpoint is paginated too (same reason as
    `/decisions`, and for the same underlying volume: one run per decision,
    already well past a sane page size on this seed), so nothing short of
    the source table itself can promise every run is accounted for.  Same
    pattern as test_editing_a_stored_entry_breaks_verification in
    test_decision_pipeline.py.
    """
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models import SimulationRun

    response = client.post("/api/v1/simulation/rebuild")
    assert response.status_code == 200

    decisions = client.get("/api/v1/decisions", params={"limit": 200}).json()

    async with AsyncSessionLocal() as session:
        run_decision_ids = set((await session.execute(select(SimulationRun.decision_id))).scalars())

    assert response.json()["rebuilt"] >= len(decisions)
    assert {d["id"] for d in decisions} <= run_decision_ids


def test_rebuilt_runs_carry_model_probabilities(client):
    client.post("/api/v1/simulation/rebuild")
    runs = client.get("/api/v1/simulations").json()

    for stored in runs:
        probabilities = [o["probability"] for o in stored["outcomes"]]
        assert sum(probabilities) == pytest.approx(1.0, abs=1e-3)
        assert sum(1 for o in stored["outcomes"] if o["recommended"]) == 1
