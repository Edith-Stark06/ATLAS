"""Unit tests for comparative benchmarking and change attribution.

A ranking is far easier to make look authoritative than to make correct, so
these concentrate on the ways it could quietly be wrong: incomparable agents
ranked anyway, an unexercised agent topping the cohort, a score built from
three decisions read as a track record, and — the important one — an
attribution whose parts do not sum to the change it claims to explain.
"""

import pytest

from app.services.benchmark_engine import (
    CRITERION_WEIGHTS,
    THIN_EVIDENCE_DECISIONS,
    AgentMetrics,
    attribute_change,
    compliance_score,
    efficiency_score,
    gaps_to_leader,
    rank_cohort,
    reliability_score,
    score_agent,
    security_score,
    speed_score,
)


def metrics(**overrides) -> AgentMetrics:
    base = dict(
        agent_id="agt-1",
        agent_name="Agent One",
        capability="Payments",
        decisions=100,
        approved=90,
        escalated=7,
        blocked=3,
        policy_checks=800,
        policy_passed=780,
        p95_latency_ms=120,
        trust_history=[80, 81, 80, 82, 81],
    )
    base.update(overrides)
    return AgentMetrics(**base)


def factor(key: str, score: float, weight: float) -> dict:
    return {"key": key, "score": score, "weight": weight}


# --- criteria measure what they claim to -------------------------------------


def test_security_falls_as_blocked_actions_rise():
    """A block means the agent proposed something it was not permitted to do."""
    clean = security_score(metrics(blocked=0, decisions=100))
    dirty = security_score(metrics(blocked=40, decisions=100))

    assert clean.score == 100.0
    assert dirty.score == 60.0


def test_security_ignores_escalations():
    """An escalation is the system working as designed. Penalising it would
    reward an agent for being merely cautious."""
    a = security_score(metrics(approved=90, escalated=10, blocked=0))
    b = security_score(metrics(approved=100, escalated=0, blocked=0))

    assert a.score == b.score


def test_efficiency_penalises_needing_a_human():
    """Escalations are the running cost of an autonomous estate."""
    autonomous = efficiency_score(metrics(approved=100, escalated=0, blocked=0))
    needy = efficiency_score(metrics(approved=50, escalated=50, blocked=0))

    assert autonomous.score == 100.0
    assert needy.score == 50.0


def test_an_unexercised_agent_does_not_score_perfect_compliance():
    """No checks recorded is no evidence, not a clean record. Scoring it 100
    would put an agent that has never done anything at the top."""
    assert compliance_score(metrics(policy_checks=0, policy_passed=0)).score == 0.0


def test_compliance_tracks_the_pass_rate():
    assert compliance_score(metrics(policy_checks=100, policy_passed=75)).score == 75.0


def test_speed_is_measured_against_a_fixed_budget():
    """Absolute, not relative to the cohort — a uniformly slow cohort must not
    contain a "fast" agent."""
    fast = speed_score(metrics(p95_latency_ms=50))
    slow = speed_score(metrics(p95_latency_ms=2000))

    assert fast.score == 100.0
    assert slow.score == 0.0


def test_speed_does_not_go_negative_past_the_budget():
    assert speed_score(metrics(p95_latency_ms=60_000)).score == 0.0


def test_reliability_distinguishes_steady_from_swinging():
    """An agent oscillating 40–90 averages the same as one steady at 65, and
    they are not the same agent."""
    steady = reliability_score(metrics(trust_history=[65] * 6))
    swinging = reliability_score(metrics(trust_history=[40, 90, 41, 89, 42, 88]))

    assert steady.score == 100.0
    assert swinging.score < 20


def test_reliability_of_a_single_reading_is_neutral_not_perfect():
    """One reading is not a trend. Scoring it 100 would reward having no
    history at all."""
    assert reliability_score(metrics(trust_history=[90])).score == 50.0


def test_every_criterion_reports_what_it_was_computed_from():
    for criterion in score_agent(metrics()).criteria:
        assert criterion.basis, f"{criterion.key} gave no basis"


# --- composite ---------------------------------------------------------------


def test_weights_sum_to_one():
    """Otherwise the composite is not on a 0–100 scale and cannot be read as
    a score."""
    assert sum(CRITERION_WEIGHTS.values()) == pytest.approx(1.0)


def test_a_perfect_agent_scores_one_hundred():
    perfect = metrics(
        decisions=100,
        approved=100,
        escalated=0,
        blocked=0,
        policy_checks=100,
        policy_passed=100,
        p95_latency_ms=50,
        trust_history=[95] * 5,
    )
    assert score_agent(perfect).composite == pytest.approx(100.0, abs=0.1)


def test_the_composite_is_the_weighted_sum_of_its_parts():
    """The score must be reconstructable from what is shown, or the breakdown
    is decoration."""
    scored = score_agent(metrics())
    assert scored.composite == pytest.approx(
        sum(c.score * c.weight for c in scored.criteria), abs=0.05
    )


def test_thin_evidence_is_flagged():
    """A 100% rate over three decisions is not a track record."""
    assert score_agent(metrics(decisions=3, approved=3, blocked=0)).thin_evidence is True
    assert score_agent(metrics(decisions=THIN_EVIDENCE_DECISIONS)).thin_evidence is False


def test_an_unproven_agent_cannot_lead_the_cohort():
    """The leader is the benchmark everyone else's gaps are measured against,
    so one lucky decision must not become the standard for the whole cohort.

    Found by looking at a real ranking: an agent with a single decision was
    topping a cohort of eleven, and flagging it in a column did nothing to
    stop it setting the bar.
    """
    lucky = metrics(
        agent_id="lucky",
        decisions=1,
        approved=1,
        escalated=0,
        blocked=0,
        policy_checks=3,
        policy_passed=3,
        p95_latency_ms=50,
    )
    proven = metrics(
        agent_id="proven",
        decisions=240,
        approved=228,
        escalated=9,
        blocked=3,
        policy_checks=720,
        policy_passed=712,
        p95_latency_ms=95,
    )

    ranking = rank_cohort([lucky, proven])

    assert ranking.leader.agent_id == "proven"
    # The unproven agent still scores higher, and the score is not doctored —
    # it simply sorts below anyone with a track record.
    lucky_scored = next(a for a in ranking.scored if a.agent_id == "lucky")
    assert lucky_scored.composite > ranking.leader.composite
    assert [a.agent_id for a in ranking.scored] == ["proven", "lucky"]


def test_a_cohort_of_only_unproven_agents_still_has_a_leader():
    """A young estate needs a benchmark too; the flag is what qualifies it."""
    ranking = rank_cohort(
        [
            metrics(agent_id="a", decisions=2, approved=2, blocked=0),
            metrics(agent_id="b", decisions=3, approved=1, blocked=2),
        ]
    )

    assert ranking.leader is not None
    assert ranking.leader.thin_evidence is True


# --- cohorts -----------------------------------------------------------------


def test_ranking_across_different_jobs_is_refused():
    """Ranking a fraud detector against a travel booker produces a number,
    and the number means nothing."""
    with pytest.raises(ValueError, match="different jobs"):
        rank_cohort([metrics(capability="Payments"), metrics(capability="Travel & Expense")])


def test_the_cohort_is_ordered_best_first():
    good = metrics(agent_id="good", blocked=0, policy_passed=800, policy_checks=800)
    bad = metrics(agent_id="bad", blocked=50, policy_passed=400, policy_checks=800)

    ranking = rank_cohort([bad, good])

    assert [a.agent_id for a in ranking.scored] == ["good", "bad"]
    assert ranking.leader.agent_id == "good"


def test_scores_are_absolute_not_normalised_within_the_cohort():
    """Normalising would make the best member 100 and the worst 0 by
    construction, so a uniformly excellent cohort would look like it had a
    failing agent."""
    a = metrics(agent_id="a", blocked=1)
    b = metrics(agent_id="b", blocked=2)

    ranking = rank_cohort([a, b])

    assert all(s.composite > 80 for s in ranking.scored), "both are good and should look it"
    assert ranking.scored[-1].composite != 0


def test_a_cohort_of_one_is_not_comparable():
    """A "ranking" of one agent is not a ranking, and the caller should not
    render it as one."""
    ranking = rank_cohort([metrics()])

    assert ranking.leader is not None
    assert ranking.comparable is False


def test_an_empty_cohort_has_no_leader():
    ranking = rank_cohort([])
    assert ranking.leader is None
    assert ranking.comparable is False


def test_the_weighting_is_published_with_the_ranking():
    """A ranking whose weighting cannot be inspected is an opinion presented
    as a measurement."""
    assert rank_cohort([metrics()]).weights == CRITERION_WEIGHTS


# --- gaps --------------------------------------------------------------------


def test_gaps_are_ranked_by_what_would_move_the_composite():
    """A 30-point speed gap (weight 0.10) matters less than a 12-point
    security gap (weight 0.30)."""
    leader = score_agent(metrics(agent_id="lead", blocked=0, p95_latency_ms=50))
    trailer = score_agent(metrics(agent_id="trail", blocked=12, p95_latency_ms=650))

    gaps = gaps_to_leader(trailer, leader)

    assert gaps[0].key == "security"
    assert gaps[0].composite_cost > next(g.composite_cost for g in gaps if g.key == "speed")


def test_criteria_where_the_agent_is_ahead_are_not_listed_as_gaps():
    leader = score_agent(metrics(agent_id="lead", blocked=5, p95_latency_ms=1500))
    faster = score_agent(metrics(agent_id="fast", blocked=5, p95_latency_ms=60))

    assert all(g.key != "speed" for g in gaps_to_leader(faster, leader))


def test_the_leader_has_no_gaps_to_itself():
    leader = score_agent(metrics())
    assert gaps_to_leader(leader, leader) == []


# --- mechanism ranking: the parts must sum to the whole ----------------------


def test_the_attribution_reconciles_to_the_actual_change():
    """The invariant the whole thing rests on. If the contributions do not sum
    to the observed delta, the breakdown is decoration."""
    before = [factor("policy", 70, 0.5), factor("risk", 60, 0.5)]
    after = [factor("policy", 90, 0.5), factor("risk", 60, 0.5)]

    result = attribute_change(
        before_factors=before,
        after_factors=after,
        before_score=65,
        after_score=75,
    )

    assert result.reconciles
    assert result.delta == 10


def test_a_factors_own_movement_is_separated_from_a_weight_change():
    """ "Policy compliance improved" and "policy compliance now counts for
    more" are different events, and a reader needs to know which happened."""
    before = [factor("policy", 70, 0.2)]
    after = [factor("policy", 70, 0.5)]

    contribution = attribute_change(
        before_factors=before, after_factors=after, before_score=14, after_score=35
    ).contributions[0]

    assert contribution.from_value == 0, "the factor itself did not move"
    assert contribution.from_weight > 0, "the weight did"


def test_a_pure_value_change_is_attributed_to_value():
    before = [factor("risk", 40, 0.5)]
    after = [factor("risk", 80, 0.5)]

    contribution = attribute_change(
        before_factors=before, after_factors=after, before_score=20, after_score=40
    ).contributions[0]

    assert contribution.from_weight == 0
    assert contribution.from_value == pytest.approx(20)


def test_contributions_are_ranked_by_magnitude_not_by_sign():
    """A large drop explains a score change as much as a large rise."""
    before = [factor("a", 50, 0.5), factor("b", 50, 0.5)]
    after = [factor("a", 55, 0.5), factor("b", 10, 0.5)]

    keys = [
        c.key
        for c in attribute_change(
            before_factors=before, after_factors=after, before_score=50, after_score=32.5
        ).contributions
    ]

    assert keys[0] == "b"


def test_unchanged_factors_are_still_reported():
    """Omitting them makes "this did not move" look like "this was never
    considered"."""
    before = [factor("a", 50, 0.5), factor("steady", 70, 0.5)]
    after = [factor("a", 60, 0.5), factor("steady", 70, 0.5)]

    result = attribute_change(
        before_factors=before, after_factors=after, before_score=60, after_score=65
    )

    steady = next(c for c in result.contributions if c.key == "steady")
    assert steady.contribution == 0


def test_a_newly_added_factor_is_attributed_not_dropped():
    """Adding a factor changes the score; the change has to land somewhere."""
    result = attribute_change(
        before_factors=[factor("a", 50, 1.0)],
        after_factors=[factor("a", 50, 0.5), factor("new", 80, 0.5)],
        before_score=50,
        after_score=65,
    )

    assert any(c.key == "new" and c.contribution != 0 for c in result.contributions)
    assert result.reconciles


def test_a_removed_factor_is_attributed():
    result = attribute_change(
        before_factors=[factor("a", 50, 0.5), factor("gone", 90, 0.5)],
        after_factors=[factor("a", 50, 1.0)],
        before_score=70,
        after_score=50,
    )

    gone = next(c for c in result.contributions if c.key == "gone")
    assert gone.contribution < 0


def test_an_anomaly_penalty_is_reported_separately():
    """It is subtracted from the base score, so it belongs to no single
    factor and must not be smeared across them."""
    result = attribute_change(
        before_factors=[factor("a", 80, 1.0)],
        after_factors=[factor("a", 80, 1.0)],
        before_score=80,
        after_score=70,
        before_penalty=0,
        after_penalty=10,
    )

    assert result.penalty_delta == 10
    assert all(c.contribution == 0 for c in result.contributions)
    assert result.reconciles


def test_an_unexplained_remainder_is_surfaced_not_hidden():
    """An attribution that silently absorbs its own error is not an
    attribution. The residual makes the discrepancy visible."""
    result = attribute_change(
        before_factors=[factor("a", 50, 1.0)],
        after_factors=[factor("a", 50, 1.0)],
        # The score moved but no factor did — something else is at work.
        before_score=50,
        after_score=62,
    )

    assert result.residual == 12
    assert result.reconciles, "reconciliation holds precisely because the gap is reported"


def test_no_change_attributes_nothing():
    factors = [factor("a", 50, 0.5), factor("b", 70, 0.5)]
    result = attribute_change(
        before_factors=factors, after_factors=factors, before_score=60, after_score=60
    )

    assert result.delta == 0
    assert result.residual == 0
    assert all(c.contribution == 0 for c in result.contributions)
