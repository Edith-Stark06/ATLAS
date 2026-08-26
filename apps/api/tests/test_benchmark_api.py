"""Comparative benchmarking against a seeded database.

The unit tests cover the scoring. These cover what only the seeded cohort can
show: that ten agents doing one job are ranked in an order the weighting
actually justifies, and that the change attribution reconciles against real
snapshots rather than hand-built ones.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest
from fastapi.testclient import TestClient

COHORT = "Customer Servicing"

#: Seeded profiles, from app/seed_cohort.py. Named here so a failure points at
#: the behaviour that broke rather than at an opaque agent id.
LEADER = "agt-cs-01"  # high volume, clean, fast
CARELESS = "agt-cs-04"  # fastest in the cohort, worst compliance
ESCALATOR = "agt-cs-09"  # escalates 38% of its work
UNSTABLE = "agt-cs-07"  # decent averages, wild trust swings
SLOW = "agt-cs-05"  # impeccable, very slow
UNPROVEN = "agt-cs-10"  # six decisions


def benchmark(client: TestClient, capability: str = COHORT, **params) -> dict:
    response = client.get(f"/api/v1/benchmark/cohorts/{capability}", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def scored_by_id(result: dict) -> dict[str, dict]:
    return {a["agentId"]: a for a in result["scored"]}


def criterion(agent: dict, key: str) -> float:
    return next(c["score"] for c in agent["criteria"] if c["key"] == key)


def rank_of(result: dict, agent_id: str) -> int:
    return [a["agentId"] for a in result["scored"]].index(agent_id)


# --- access ------------------------------------------------------------------


def test_benchmarking_requires_credentials(api: TestClient):
    assert api.get("/api/v1/benchmark/cohorts").status_code == 401
    assert api.get(f"/api/v1/benchmark/cohorts/{COHORT}").status_code == 401


# --- cohorts -----------------------------------------------------------------


def test_cohorts_are_listed_largest_first(client: TestClient):
    cohorts = client.get("/api/v1/benchmark/cohorts").json()

    assert cohorts
    counts = [c["agents"] for c in cohorts]
    assert counts == sorted(counts, reverse=True)


def test_the_seeded_cohort_is_big_enough_to_rank(client: TestClient):
    """The whole feature needs a real cohort; one agent per capability cannot
    demonstrate a ranking."""
    cohorts = {c["capability"]: c["agents"] for c in client.get("/api/v1/benchmark/cohorts").json()}
    assert cohorts.get(COHORT, 0) >= 10


def test_an_unknown_cohort_is_a_404(client: TestClient):
    assert client.get("/api/v1/benchmark/cohorts/Nonexistent%20Job").status_code == 404


# --- the ranking is justified by the weighting -------------------------------


def test_the_cohort_is_ordered_by_composite_within_evidence_class(client: TestClient):
    result = benchmark(client)
    established = [a["composite"] for a in result["scored"] if not a["thinEvidence"]]

    assert established == sorted(established, reverse=True)


def test_fast_but_careless_ranks_below_slower_but_compliant_agents(client: TestClient):
    """The seeded Rapid Triage agent is the fastest in the cohort and the
    worst on compliance. If speed carried the day the weighting would be
    wrong."""
    result = benchmark(client)
    agents = scored_by_id(result)

    careless = agents[CARELESS]
    assert criterion(careless, "speed") == max(
        criterion(a, "speed") for a in result["scored"] if not a["thinEvidence"]
    ), "this agent is supposed to be the fastest"

    assert rank_of(result, CARELESS) > rank_of(result, LEADER)


def test_an_agent_that_escalates_everything_scores_badly_on_efficiency(client: TestClient):
    """Escalations are the running cost of an autonomous estate."""
    agents = scored_by_id(benchmark(client))

    assert criterion(agents[ESCALATOR], "efficiency") < 70
    # It is not unsafe — just expensive. Security should stay high.
    assert criterion(agents[ESCALATOR], "security") > 95


def test_an_unstable_agent_is_caught_by_reliability(client: TestClient):
    """Averages hide a swing between 58 and 94. Reliability is the only
    criterion that sees it."""
    agents = scored_by_id(benchmark(client))

    assert criterion(agents[UNSTABLE], "reliability") < criterion(agents[LEADER], "reliability")


def test_a_very_slow_agent_is_penalised_on_speed_alone(client: TestClient):
    agents = scored_by_id(benchmark(client))
    slow = agents[SLOW]

    assert criterion(slow, "speed") < 20
    # Clean on everything else, which is the point of the case.
    assert criterion(slow, "security") == 100
    assert criterion(slow, "compliance") == 100


# --- evidence ----------------------------------------------------------------


def test_an_unproven_agent_cannot_be_the_benchmark(client: TestClient):
    """The leader sets the bar every other agent is measured against, so it
    must have a track record."""
    result = benchmark(client)
    agents = scored_by_id(result)

    assert agents[UNPROVEN]["thinEvidence"] is True
    assert result["leaderId"] != UNPROVEN
    assert agents[result["leaderId"]]["thinEvidence"] is False


def test_unproven_agents_sort_below_established_ones(client: TestClient):
    result = benchmark(client)
    flags = [a["thinEvidence"] for a in result["scored"]]

    # All False before all True — established first, unproven after.
    assert flags == sorted(flags)


def test_an_unproven_agents_real_score_is_still_shown(client: TestClient):
    """Sorted down, not doctored. Hiding the score would be a different lie
    from over-trusting it."""
    agents = scored_by_id(benchmark(client))
    assert agents[UNPROVEN]["composite"] > 0


# --- transparency ------------------------------------------------------------


def test_the_weighting_is_published(client: TestClient):
    """A ranking whose weighting cannot be inspected is an opinion presented
    as a measurement."""
    weights = benchmark(client)["weights"]

    assert sum(weights.values()) == pytest.approx(1.0)
    assert set(weights) == {"security", "compliance", "efficiency", "reliability", "speed"}


def test_the_composite_can_be_reconstructed_from_what_is_shown(client: TestClient):
    for agent in benchmark(client)["scored"]:
        rebuilt = sum(c["score"] * c["weight"] for c in agent["criteria"])
        assert agent["composite"] == pytest.approx(rebuilt, abs=0.05), agent["agentId"]


def test_every_criterion_states_its_basis(client: TestClient):
    for agent in benchmark(client)["scored"]:
        for c in agent["criteria"]:
            assert c["basis"], f"{agent['agentId']}/{c['key']} gave no basis"


# --- gaps --------------------------------------------------------------------


def test_gaps_point_at_what_would_move_the_score(client: TestClient):
    """The slow-but-perfect agent should be told to fix speed, not
    compliance — it already has perfect compliance."""
    result = benchmark(client)
    gaps = result["gaps"].get(SLOW, [])

    assert gaps, "a trailing agent should have gaps to the leader"
    assert gaps[0]["key"] == "speed"
    costs = [g["compositeCost"] for g in gaps]
    assert costs == sorted(costs, reverse=True)


def test_the_leader_has_no_gaps(client: TestClient):
    result = benchmark(client)
    assert result["leaderId"] not in result["gaps"]


# --- mechanism ranking -------------------------------------------------------


def test_change_attribution_reconciles_against_real_snapshots(client: TestClient):
    """The invariant, exercised on data the seeder produced rather than on
    hand-built factors."""
    result = client.get(f"/api/v1/benchmark/agents/{UNSTABLE}/changes", params={"days": 60})
    assert result.status_code == 200

    body = result.json()
    assert body["reconciles"] is True

    attributed = sum(c["contribution"] for c in body["contributions"])
    assert attributed - body["penaltyDelta"] + body["residual"] == pytest.approx(
        body["delta"], abs=0.02
    )


def test_contributions_name_the_factor_and_both_of_its_values(client: TestClient):
    body = client.get(f"/api/v1/benchmark/agents/{UNSTABLE}/changes", params={"days": 60}).json()

    assert body["contributions"]
    for c in body["contributions"]:
        assert c["label"]
        assert "before" in c and "after" in c
        # The split must add up to the whole for each factor.
        assert c["fromValue"] + c["fromWeight"] == pytest.approx(c["contribution"], abs=0.01)


def test_the_unexplained_share_is_reported(client: TestClient):
    """The score comes from a trained model, not the weighted sum this
    decomposition assumes, so part of a change is often unattributable — and
    saying so is more useful than spreading it across the factors."""
    body = client.get(f"/api/v1/benchmark/agents/{UNSTABLE}/changes", params={"days": 60}).json()

    assert 0.0 <= body["residualShare"] <= 1.0


def test_a_window_with_too_little_history_invents_no_change(client: TestClient):
    """A one-day window usually holds fewer than two snapshots, and the
    service must say "nothing to compare" rather than fabricate a delta.

    Asserted as an invariant rather than as a fixed expectation: other tests
    in the suite call /trust/recompute, which writes a snapshot at "now" for
    every agent. How many land inside a one-day window therefore depends on
    execution order, and an earlier version of this test asserted an empty
    result and passed or failed on that ordering alone.
    """
    body = client.get(f"/api/v1/benchmark/agents/{UNPROVEN}/changes", params={"days": 1}).json()

    if not body["contributions"]:
        # The "no history" path: no change may be claimed from no evidence.
        assert body["delta"] == 0
        assert body["residual"] == 0
    else:
        # Enough snapshots to compare after all — then the ordinary guarantee
        # applies, and the parts must still sum to the whole.
        assert body["reconciles"] is True


def test_an_unknown_agent_is_a_404(client: TestClient):
    assert client.get("/api/v1/benchmark/agents/agt-nope/changes").status_code == 404
