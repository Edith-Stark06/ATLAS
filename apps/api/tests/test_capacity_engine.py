"""Unit tests for capacity planning.

A scaling plan is easy to make look confident. These concentrate on the ways
it would quietly mislead: recommending growth for an agent that is failing,
reporting a target as reachable when reviewers are the thing that runs out,
planning on an agent with six decisions behind it, and presenting assumptions
as findings.
"""

import pytest

from app.services.capacity_engine import (
    DEFAULT_REVIEW_MINUTES,
    LATENCY_BUDGET_MS,
    MAX_SHARE_GROWTH,
    QUALITY_FLOOR,
    REVIEW_MINUTES_PER_DAY,
    AgentCapacity,
    Constraint,
    build_plan,
    plan_agent,
    reviewer_days_needed,
)


def agent(**overrides) -> AgentCapacity:
    base = dict(
        agent_id="agt-1",
        agent_name="Agent One",
        decisions=300,
        escalated=30,
        blocked=6,
        p95_latency_ms=180,
        composite=90.0,
        security=99.0,
        compliance=99.0,
        thin_evidence=False,
    )
    base.update(overrides)
    return AgentCapacity(**base)


def plan(cohort=None, **overrides):
    kwargs = dict(
        capability="Customer Servicing",
        cohort=cohort if cohort is not None else [agent()],
        window_days=30,
        multiplier=3.0,
        reviewer_days_available=10.0,
    )
    kwargs.update(overrides)
    return build_plan(**kwargs)


# --- reviewer arithmetic -----------------------------------------------------


def test_reviewer_days_scale_with_escalations():
    one = reviewer_days_needed(100, review_minutes=12)
    two = reviewer_days_needed(200, review_minutes=12)

    assert two == pytest.approx(one * 2)


def test_reviewer_days_use_a_realistic_working_day():
    """Planning against a full eight hours produces a rota that fails on
    contact with reality."""
    assert REVIEW_MINUTES_PER_DAY < 480

    needed = reviewer_days_needed(REVIEW_MINUTES_PER_DAY / DEFAULT_REVIEW_MINUTES)
    assert needed == pytest.approx(1.0, abs=0.01)


def test_no_escalations_need_no_reviewers():
    assert reviewer_days_needed(0) == 0.0


# --- constraints -------------------------------------------------------------


def test_a_constraint_with_spare_capacity_is_satisfied():
    c = Constraint(key="k", label="L", available=10, required=5, unit="u", detail="")

    assert c.satisfied is True
    assert c.headroom == pytest.approx(1.0)
    assert c.shortfall == 0


def test_a_shortfall_is_reported_and_headroom_does_not_go_negative():
    """Negative headroom reads as a percentage and would be misleading; the
    shortfall carries the bad news in the unit that matters."""
    c = Constraint(key="k", label="L", available=4, required=10, unit="u", detail="")

    assert c.satisfied is False
    assert c.headroom == 0.0
    assert c.shortfall == 6


def test_a_constraint_that_needs_nothing_has_full_headroom():
    c = Constraint(key="k", label="L", available=0, required=0, unit="u", detail="")
    assert c.headroom == 1.0


# --- the binding constraint is the point -------------------------------------


def test_the_binding_constraint_is_the_one_that_runs_out_first():
    """Adding agents does not help when what you are short of is reviewers."""
    result = plan(
        cohort=[agent(decisions=3000, escalated=900)],
        reviewer_days_available=1.0,
    )

    assert result.binding is not None
    assert result.binding.key == "human_review"
    assert result.feasible is False


def test_trusted_capacity_binds_when_the_cohort_is_mostly_weak():
    """Plenty of reviewers, but nobody fit to hand the work to."""
    result = plan(
        cohort=[
            agent(agent_id="good", composite=92.0, decisions=100, escalated=2),
            agent(agent_id="bad-1", composite=55.0, decisions=400, escalated=4),
            agent(agent_id="bad-2", composite=51.0, decisions=400, escalated=4),
        ],
        multiplier=5.0,
        reviewer_days_available=500.0,
    )

    assert result.binding.key == "trusted_throughput"


def test_a_comfortable_target_is_feasible():
    result = plan(multiplier=1.2, reviewer_days_available=50.0)
    assert result.feasible is True


def test_a_slow_agent_does_not_veto_the_plan_for_everyone_else():
    """Latency is measured across the agents actually taking load.

    An earlier version took the slowest agent in the whole cohort, so one slow
    agent nobody was scaling made every plan permanently infeasible — which is
    how a constraint stops being information and becomes noise.
    """
    result = plan(
        cohort=[
            agent(agent_id="quick", p95_latency_ms=200),
            agent(agent_id="glacial", p95_latency_ms=LATENCY_BUDGET_MS * 2),
        ],
        multiplier=1.2,
        reviewer_days_available=100.0,
    )

    latency = next(c for c in result.constraints if c.key == "latency_budget")
    assert latency.required == 200, "should measure only the agent being grown"

    by_id = {a.agent_id: a for a in result.agents}
    assert by_id["glacial"].action == "hold"
    assert by_id["quick"].action == "scale"


def test_latency_binds_when_the_growing_agents_are_near_the_budget():
    """Satisfied but tight is still the binding constraint — `binding` picks
    the least headroom, not the first outright failure."""
    result = plan(
        cohort=[agent(p95_latency_ms=LATENCY_BUDGET_MS - 20)],
        multiplier=1.05,
        reviewer_days_available=10_000.0,
    )

    assert result.binding.key == "latency_budget"
    assert result.binding.satisfied is True


# --- quality gates growth ----------------------------------------------------


def test_a_failing_agent_is_told_to_fix_before_it_grows():
    """Three times the volume through an agent that blocks 9% of its actions
    is three times the blocked actions, not a capacity win."""
    result = plan_agent(
        agent(composite=QUALITY_FLOOR - 10, blocked=27, decisions=300),
        window_days=30,
        growth_share=999.0,
    )

    assert result.action == "fix_first"
    assert result.recommended_daily == result.current_daily
    assert "multiplies the failures" in result.reason


def test_a_strong_agent_is_offered_more_work():
    result = plan_agent(agent(composite=95.0), window_days=30, growth_share=999.0)

    assert result.action == "scale"
    assert result.recommended_daily > result.current_daily


def test_an_unproven_agent_is_observed_not_planned_on():
    """Six decisions is not a throughput measurement."""
    result = plan_agent(agent(decisions=6, thin_evidence=True), window_days=30, growth_share=999.0)

    assert result.action == "observe"
    assert result.recommended_daily == result.current_daily


def test_a_slow_agent_is_held_even_when_its_quality_is_good():
    result = plan_agent(
        agent(composite=95.0, p95_latency_ms=LATENCY_BUDGET_MS + 1),
        window_days=30,
        growth_share=999.0,
    )

    assert result.action == "hold"
    assert str(LATENCY_BUDGET_MS) in result.reason


def test_growth_is_capped_at_something_an_operations_team_can_stand_up():
    """Nobody triples an agent's load overnight."""
    result = plan_agent(agent(composite=99.0), window_days=30, growth_share=1_000_000.0)

    assert result.recommended_daily <= result.current_daily * MAX_SHARE_GROWTH


def test_the_change_percentage_is_reported():
    result = plan_agent(agent(composite=95.0), window_days=30, growth_share=999.0)
    assert result.change_pct == pytest.approx((MAX_SHARE_GROWTH - 1) * 100, abs=1)


# --- allocation --------------------------------------------------------------


def test_the_better_agent_is_given_the_larger_share():
    """Quality earns load. Scaling whoever is already busiest is what created
    the problem."""
    result = plan(
        cohort=[
            agent(agent_id="strong", composite=96.0, decisions=300),
            agent(agent_id="weaker", composite=82.0, decisions=300),
        ],
        multiplier=1.5,
        reviewer_days_available=100.0,
    )

    by_id = {a.agent_id: a for a in result.agents}
    assert by_id["strong"].recommended_daily >= by_id["weaker"].recommended_daily


def test_problems_are_listed_before_successes():
    """A reader opening a scaling plan wants what is wrong with it."""
    result = plan(
        cohort=[
            agent(agent_id="fine", composite=95.0),
            agent(agent_id="broken", composite=40.0),
            agent(agent_id="new", decisions=4, thin_evidence=True),
        ],
        reviewer_days_available=100.0,
    )

    assert result.agents[0].agent_id == "broken"


def test_volume_nobody_can_safely_take_is_surfaced():
    """A plan that quietly falls short of its own target is worse than one
    that says so."""
    result = plan(
        cohort=[agent(agent_id="only", composite=40.0, decisions=300)],
        multiplier=4.0,
        reviewer_days_available=100.0,
    )

    assert result.unallocated_daily > 0


def test_every_agent_gets_a_reason():
    result = plan(
        cohort=[
            agent(agent_id="a", composite=95.0),
            agent(agent_id="b", composite=40.0),
            agent(agent_id="c", decisions=3, thin_evidence=True),
        ]
    )

    for entry in result.agents:
        assert entry.reason, f"{entry.agent_id} was given no reason"


# --- honesty about the model -------------------------------------------------


def test_assumptions_are_stated_not_buried():
    result = plan()
    joined = " ".join(result.assumptions).lower()

    assert "minutes" in joined
    # The load-dependence caveat matters most: rates measured under light load
    # are the least safe thing being extrapolated.
    assert "do not always survive heavy load" in joined


def test_what_atlas_cannot_answer_is_declared():
    """ATLAS observes decisions, not servers. A capacity plan that stays quiet
    about that invites being mistaken for a full one."""
    joined = " ".join(plan().out_of_scope).lower()

    assert "infrastructure" in joined
    assert "cost" in joined


def test_the_review_time_assumption_is_overridable():
    """It is the biggest lever on the reviewer figure, so a team that has
    measured their own should be able to use it."""
    slow = plan(review_minutes=30.0)
    fast = plan(review_minutes=5.0)

    slow_review = next(c for c in slow.constraints if c.key == "human_review")
    fast_review = next(c for c in fast.constraints if c.key == "human_review")

    assert slow_review.required > fast_review.required


# --- degenerate inputs -------------------------------------------------------


def test_an_empty_cohort_does_not_divide_by_zero():
    result = plan(cohort=[], reviewer_days_available=1.0)

    assert result.current_daily == 0
    assert result.target_daily == 0
    assert result.agents == []


def test_a_multiplier_below_one_is_clamped():
    """This plans for growth. "Scale to 50%" is a different question and
    silently answering it would be wrong."""
    assert plan(multiplier=0.2).multiplier == 1.0


def test_a_zero_day_window_is_clamped():
    assert plan(window_days=0).window_days == 1
