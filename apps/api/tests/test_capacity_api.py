"""Capacity planning against the seeded cohort.

The unit tests cover the arithmetic. These cover what only real data can
show: that the plan agrees with the benchmark about who is failing, that the
binding constraint moves when the operator's own figures move, and that a
target the estate cannot reach is reported as unreachable.

Skips when Postgres is unreachable; see tests/test_governance.py.
"""

import pytest
from fastapi.testclient import TestClient

COHORT = "Customer Servicing"

CARELESS = "agt-cs-04"  # worst compliance in the seeded cohort
UNPROVEN = "agt-cs-10"  # six decisions
SLOW = "agt-cs-05"  # 1450ms centre latency


def plan(client: TestClient, **overrides) -> dict:
    payload = {
        "capability": COHORT,
        "multiplier": 3.0,
        "days": 30,
        "reviewerDaysAvailable": 5.0,
        "reviewMinutes": 12.0,
    }
    payload.update(overrides)
    response = client.post("/api/v1/capacity/plan", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def by_id(result: dict) -> dict[str, dict]:
    return {a["agentId"]: a for a in result["agents"]}


# --- access ------------------------------------------------------------------


def test_capacity_planning_requires_credentials(api: TestClient):
    response = api.post("/api/v1/capacity/plan", json={"capability": COHORT})
    assert response.status_code == 401


def test_an_unknown_cohort_is_a_404(client: TestClient):
    response = client.post(
        "/api/v1/capacity/plan", json={"capability": "Nonexistent Job", "multiplier": 2}
    )
    assert response.status_code == 404


# --- the projection is grounded in real throughput ---------------------------


def test_the_target_is_the_current_volume_times_the_multiplier(client: TestClient):
    result = plan(client, multiplier=3.0)

    assert result["currentDaily"] > 0
    assert result["targetDaily"] == pytest.approx(result["currentDaily"] * 3, rel=0.01)


def test_every_agent_in_the_cohort_is_accounted_for(client: TestClient):
    result = plan(client)
    cohort = client.get(f"/api/v1/benchmark/cohorts/{COHORT}").json()

    assert len(result["agents"]) == len(cohort["scored"])


def test_a_bigger_multiplier_demands_more_review(client: TestClient):
    small = plan(client, multiplier=1.5)
    large = plan(client, multiplier=6.0)

    def review(result):
        return next(c for c in result["constraints"] if c["key"] == "human_review")

    assert review(large)["required"] > review(small)["required"]


# --- the binding constraint is the answer ------------------------------------


def test_starving_review_makes_it_the_binding_constraint(client: TestClient):
    """Adding agents does not help when what runs out is human review."""
    result = plan(client, multiplier=5.0, reviewerDaysAvailable=0.1)

    assert result["bindingConstraint"] == "human_review"
    assert result["feasible"] is False


def test_ample_review_moves_the_constraint_elsewhere(client: TestClient):
    """With reviewers no longer scarce, the limit becomes who is fit to take
    the work."""
    result = plan(client, multiplier=8.0, reviewerDaysAvailable=10_000.0)

    assert result["bindingConstraint"] != "human_review"


def test_a_shortfall_is_reported_in_real_units(client: TestClient):
    result = plan(client, multiplier=10.0, reviewerDaysAvailable=0.1)
    review = next(c for c in result["constraints"] if c["key"] == "human_review")

    assert review["shortfall"] > 0
    assert review["unit"] == "reviewer-days/day"
    # Headroom floors at zero rather than going negative, which would read as
    # a nonsensical percentage.
    assert review["headroom"] == 0


def test_a_modest_target_is_reachable(client: TestClient):
    result = plan(client, multiplier=1.1, reviewerDaysAvailable=100.0)
    assert result["feasible"] is True


# --- the plan agrees with the benchmark --------------------------------------


def test_the_worst_agent_is_told_to_fix_before_it_grows(client: TestClient):
    """The seeded Rapid Triage agent has the cohort's worst compliance. A
    capacity plan that offered it more volume would contradict the benchmark
    screen built on the same records."""
    result = plan(client, reviewerDaysAvailable=1000.0)
    careless = by_id(result)[CARELESS]

    assert careless["action"] == "fix_first"
    assert careless["recommendedDaily"] == careless["currentDaily"]


def test_an_unproven_agent_is_observed_not_planned_on(client: TestClient):
    result = plan(client, reviewerDaysAvailable=1000.0)
    assert by_id(result)[UNPROVEN]["action"] == "observe"


def test_no_agent_is_asked_to_shrink(client: TestClient):
    """This plans for growth; a recommendation below current volume would be
    answering a question nobody asked."""
    for entry in plan(client)["agents"]:
        assert entry["recommendedDaily"] >= entry["currentDaily"], entry["agentId"]


def test_growth_is_capped_at_double(client: TestClient):
    for entry in plan(client, multiplier=15.0, reviewerDaysAvailable=10_000.0)["agents"]:
        if entry["currentDaily"] > 0:
            assert entry["recommendedDaily"] <= entry["currentDaily"] * 2 + 0.01


def test_volume_nobody_can_take_is_surfaced(client: TestClient):
    """A plan that quietly falls short of its own target is worse than one
    that says so."""
    result = plan(client, multiplier=15.0, reviewerDaysAvailable=10_000.0)
    assert result["unallocatedDaily"] > 0


def test_problems_are_listed_first(client: TestClient):
    """A reader opening a scaling plan wants what is wrong with it."""
    actions = [a["action"] for a in plan(client, reviewerDaysAvailable=1000.0)["agents"]]

    if "fix_first" in actions and "scale" in actions:
        assert actions.index("fix_first") < actions.index("scale")


def test_every_recommendation_carries_its_reasoning(client: TestClient):
    for entry in plan(client)["agents"]:
        assert entry["reason"], f"{entry['agentId']} was given no reason"


# --- honesty -----------------------------------------------------------------


def test_the_operators_own_review_time_changes_the_answer(client: TestClient):
    """It is the biggest lever on the reviewer figure, so it must be theirs
    to set rather than baked in."""
    quick = plan(client, reviewMinutes=3.0)
    slow = plan(client, reviewMinutes=45.0)

    def review(result):
        return next(c for c in result["constraints"] if c["key"] == "human_review")

    assert review(slow)["required"] > review(quick)["required"] * 5


def test_the_assumptions_are_returned_with_the_plan(client: TestClient):
    joined = " ".join(plan(client)["assumptions"]).lower()

    assert "minutes" in joined
    # The load-dependence caveat is the least safe extrapolation in here.
    assert "heavy load" in joined


def test_what_atlas_cannot_answer_is_declared(client: TestClient):
    """ATLAS observes decisions, not servers. Staying quiet about that invites
    the plan being mistaken for a full one."""
    joined = " ".join(plan(client)["outOfScope"]).lower()

    assert "infrastructure" in joined
    assert "cost" in joined


def test_a_shrink_multiplier_is_refused(client: TestClient):
    """Scaling down is a different question with the same shape; answering it
    silently would be wrong."""
    response = client.post("/api/v1/capacity/plan", json={"capability": COHORT, "multiplier": 0.5})
    assert response.status_code == 422


def test_an_absurd_multiplier_is_refused(client: TestClient):
    """Every rate in the plan was measured at today's volume. Past a point the
    extrapolation is fantasy."""
    response = client.post("/api/v1/capacity/plan", json={"capability": COHORT, "multiplier": 5000})
    assert response.status_code == 422
