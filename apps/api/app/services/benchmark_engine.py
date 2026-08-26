"""Comparative evaluation: which agent doing this job is the best one?

Everything before this scores an agent in isolation — is *this* action safe.
This answers a different question an operator actually asks: given ten agents
doing the same job, which should get more of the work, and what would the
others have to change to catch up.

Two rules govern the whole module, because a ranking is far easier to make
look authoritative than to make correct:

- **Only comparable things are compared.** Agents are ranked within a cohort
  doing the same job. Ranking a fraud detector against a travel booker
  produces a number, and the number means nothing.
- **Scores are absolute, not normalised within the cohort.** Normalising to
  the cohort makes the best member 100 and the worst 0 *by construction* — an
  excellent estate looks like it has a failing agent, and a failing estate
  looks like it has an excellent one. The scales here are fixed, so a cohort
  where everyone scores 90 is visibly a good cohort.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

#: Weighting of each criterion in the composite. Returned with every ranking
#: rather than kept private: a ranking whose weighting cannot be inspected is
#: an opinion presented as a measurement.
CRITERION_WEIGHTS: dict[str, float] = {
    "security": 0.30,
    "compliance": 0.25,
    "efficiency": 0.20,
    "reliability": 0.15,
    "speed": 0.10,
}

CRITERION_LABELS: dict[str, str] = {
    "security": "Security",
    "compliance": "Compliance",
    "efficiency": "Efficiency",
    "reliability": "Reliability",
    "speed": "Speed",
}

#: Latency budget for the speed score, in milliseconds. p95 at or under
#: `FAST_MS` scores 100; at or over `SLOW_MS` scores 0. Fixed rather than
#: relative to the cohort so a uniformly slow cohort does not contain a
#: "fast" agent.
FAST_MS = 50
SLOW_MS = 2000

#: Below this many decisions, an agent's rates are not a measurement. Ranked
#: anyway — excluding it would hide a new agent entirely — but flagged, so a
#: 100% score over three decisions is not read as a track record.
THIN_EVIDENCE_DECISIONS = 25


@dataclass(frozen=True)
class AgentMetrics:
    """Raw observations for one agent over the comparison window."""

    agent_id: str
    agent_name: str
    capability: str

    decisions: int
    approved: int
    escalated: int
    blocked: int

    policy_checks: int
    policy_passed: int

    #: 95th percentile decision latency, milliseconds.
    p95_latency_ms: int

    #: Trust scores over the window, oldest first. Used for stability.
    trust_history: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class CriterionScore:
    key: str
    label: str
    #: 0–100, absolute.
    score: float
    weight: float
    #: What the score was computed from, in the unit an operator recognises.
    basis: str

    @property
    def contribution(self) -> float:
        return round(self.score * self.weight, 2)


@dataclass(frozen=True)
class AgentScore:
    agent_id: str
    agent_name: str
    capability: str
    composite: float
    criteria: list[CriterionScore]
    decisions: int
    #: True when there is too little activity for the rates to mean much.
    thin_evidence: bool

    def criterion(self, key: str) -> CriterionScore | None:
        return next((c for c in self.criteria if c.key == key), None)


@dataclass(frozen=True)
class Gap:
    """What separates an agent from the cohort leader, per criterion."""

    key: str
    label: str
    agent_score: float
    leader_score: float
    #: How much of the composite gap this criterion accounts for.
    composite_cost: float

    @property
    def points(self) -> float:
        return round(self.leader_score - self.agent_score, 2)


@dataclass(frozen=True)
class Ranking:
    capability: str
    weights: dict[str, float]
    scored: list[AgentScore]
    #: Best agent in the cohort, or None when the cohort is empty.
    leader: AgentScore | None
    #: Only meaningful with at least two members; a "ranking" of one is not one.
    comparable: bool


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


# --- individual criteria -----------------------------------------------------


def security_score(metrics: AgentMetrics) -> CriterionScore:
    """How often the agent attempts something the rules forbid.

    Measured on *blocked* decisions rather than on escalations: an escalation
    is the system working as designed, while a block means the agent proposed
    an action it was not permitted to take. Those are different signals and
    collapsing them would reward an agent for being merely cautious.
    """
    blocked_rate = _rate(metrics.blocked, metrics.decisions)
    score = _clamp(100 * (1 - blocked_rate))

    return CriterionScore(
        key="security",
        label=CRITERION_LABELS["security"],
        score=round(score, 2),
        weight=CRITERION_WEIGHTS["security"],
        basis=f"{metrics.blocked} of {metrics.decisions} actions blocked",
    )


def compliance_score(metrics: AgentMetrics) -> CriterionScore:
    """Share of individual policy checks the agent passed.

    Finer-grained than the blocked rate: an action can clear the gate while
    still tripping a review rule, and an agent that repeatedly grazes the
    rules is behaving differently from one that never does.
    """
    pass_rate = _rate(metrics.policy_passed, metrics.policy_checks)
    # No checks recorded is not perfect compliance; it is no evidence. Scoring
    # it 100 would put an unexercised agent at the top of the cohort.
    score = 100 * pass_rate if metrics.policy_checks else 0.0

    return CriterionScore(
        key="compliance",
        label=CRITERION_LABELS["compliance"],
        score=round(_clamp(score), 2),
        weight=CRITERION_WEIGHTS["compliance"],
        basis=(
            f"{metrics.policy_passed} of {metrics.policy_checks} policy checks passed"
            if metrics.policy_checks
            else "no policy checks recorded"
        ),
    )


def efficiency_score(metrics: AgentMetrics) -> CriterionScore:
    """How much of the agent's work completes without a human.

    Escalations are the real running cost of an autonomous estate — each one
    is someone's time. An agent that escalates half its work is not
    autonomous, whatever its trust score says.
    """
    autonomy = _rate(metrics.approved, metrics.decisions)

    return CriterionScore(
        key="efficiency",
        label=CRITERION_LABELS["efficiency"],
        score=round(_clamp(100 * autonomy), 2),
        weight=CRITERION_WEIGHTS["efficiency"],
        basis=f"{metrics.escalated} of {metrics.decisions} actions needed a human",
    )


def speed_score(metrics: AgentMetrics) -> CriterionScore:
    """Decision latency against a fixed budget.

    p95, not mean — the governance gate sits in front of a live action, so
    what matters is the slow end. The budget is absolute so a uniformly slow
    cohort does not contain a "fast" agent by comparison.
    """
    p95 = metrics.p95_latency_ms
    if p95 <= 0:
        score = 0.0
        basis = "no latency recorded"
    else:
        span = SLOW_MS - FAST_MS
        score = _clamp(100 * (1 - (p95 - FAST_MS) / span))
        basis = f"p95 {p95}ms against a {FAST_MS}–{SLOW_MS}ms budget"

    return CriterionScore(
        key="speed",
        label=CRITERION_LABELS["speed"],
        score=round(score, 2),
        weight=CRITERION_WEIGHTS["speed"],
        basis=basis,
    )


def reliability_score(metrics: AgentMetrics) -> CriterionScore:
    """How steady the agent's trust has been.

    Population standard deviation of its trust history, inverted. An agent
    oscillating between 40 and 90 averages the same as one holding steady at
    65, and they are not the same agent — the first is unpredictable, and
    unpredictability is the thing governance exists to catch.
    """
    history = metrics.trust_history
    if len(history) < 2:
        # One reading is not a trend. Neutral rather than perfect: claiming
        # stability from a single sample would reward having no history.
        return CriterionScore(
            key="reliability",
            label=CRITERION_LABELS["reliability"],
            score=50.0,
            weight=CRITERION_WEIGHTS["reliability"],
            basis="not enough history to judge stability",
        )

    mean = sum(history) / len(history)
    variance = sum((value - mean) ** 2 for value in history) / len(history)
    stdev = math.sqrt(variance)

    # 0 points of swing scores 100; 25 points or more scores 0.
    score = _clamp(100 * (1 - stdev / 25))

    return CriterionScore(
        key="reliability",
        label=CRITERION_LABELS["reliability"],
        score=round(score, 2),
        weight=CRITERION_WEIGHTS["reliability"],
        basis=f"trust swing of ±{stdev:.1f} points over {len(history)} readings",
    )


SCORERS = (
    security_score,
    compliance_score,
    efficiency_score,
    reliability_score,
    speed_score,
)


def score_agent(metrics: AgentMetrics) -> AgentScore:
    criteria = [scorer(metrics) for scorer in SCORERS]
    composite = sum(c.contribution for c in criteria)

    return AgentScore(
        agent_id=metrics.agent_id,
        agent_name=metrics.agent_name,
        capability=metrics.capability,
        composite=round(composite, 2),
        criteria=criteria,
        decisions=metrics.decisions,
        thin_evidence=metrics.decisions < THIN_EVIDENCE_DECISIONS,
    )


# --- cohort ------------------------------------------------------------------


def rank_cohort(cohort: list[AgentMetrics]) -> Ranking:
    """Rank agents doing the same job, best first.

    Raises if the cohort mixes capabilities. That is a programming error
    rather than a data condition: silently ranking a fraud detector against a
    travel booker would produce a confident, meaningless ordering, and the
    caller would have no way to tell.
    """
    capabilities = {m.capability for m in cohort}
    if len(capabilities) > 1:
        raise ValueError(
            f"cannot rank across different jobs: {sorted(capabilities)}. "
            "Agents are only comparable within a capability."
        )

    # Established agents rank above unproven ones regardless of score.
    #
    # Flagging thin evidence in a column is not enough on its own: the leader
    # is the benchmark every other agent's gaps are measured against, so an
    # agent with one lucky decision would become the standard the whole cohort
    # is held to. Its score is still shown truthfully — it just cannot lead on
    # the strength of a sample that proves nothing.
    scored = sorted(
        (score_agent(m) for m in cohort),
        key=lambda a: (not a.thin_evidence, a.composite, a.decisions),
        reverse=True,
    )

    established = [a for a in scored if not a.thin_evidence]

    return Ranking(
        capability=next(iter(capabilities), ""),
        weights=dict(CRITERION_WEIGHTS),
        scored=scored,
        # Falls back to the top of the whole list only when nobody in the
        # cohort has a track record — a young estate still needs a leader,
        # and the thin-evidence flag is there to qualify it.
        leader=established[0] if established else (scored[0] if scored else None),
        comparable=len(scored) >= 2,
    )


def gaps_to_leader(agent: AgentScore, leader: AgentScore) -> list[Gap]:
    """Where an agent loses ground to the cohort leader, biggest first.

    Weighted by criterion, so the list is ordered by what would actually move
    the composite rather than by raw point difference — closing a 30-point gap
    on speed (weight 0.10) matters less than closing a 12-point gap on
    security (weight 0.30).
    """
    gaps: list[Gap] = []

    for criterion in agent.criteria:
        peer = leader.criterion(criterion.key)
        if peer is None or peer.score <= criterion.score:
            continue

        gaps.append(
            Gap(
                key=criterion.key,
                label=criterion.label,
                agent_score=criterion.score,
                leader_score=peer.score,
                composite_cost=round((peer.score - criterion.score) * criterion.weight, 2),
            )
        )

    return sorted(gaps, key=lambda g: g.composite_cost, reverse=True)


# --- mechanism ranking: what changed, and how much did it matter -------------


@dataclass(frozen=True)
class Contribution:
    """One factor's share of a score change."""

    key: str
    label: str
    before: float
    after: float
    #: Points of the total score change attributable to this factor. Signed.
    contribution: float
    #: Split of the above: how much came from the factor's own movement
    #: versus from its weight being re-tuned.
    from_value: float
    from_weight: float

    @property
    def improved(self) -> bool:
        return self.contribution > 0


@dataclass(frozen=True)
class ChangeAttribution:
    """Why an agent's score moved between two points in time."""

    before_score: float
    after_score: float
    delta: float
    contributions: list[Contribution]
    #: Change in the anomaly penalty, which is subtracted from the base score
    #: and so is not attributable to any single factor.
    penalty_delta: float
    #: Whatever the decomposition does not account for — rounding, or a term
    #: the model applies that this does not know about. Reported rather than
    #: spread across the factors, because an attribution that silently
    #: absorbs its own error is not an attribution.
    residual: float

    @property
    def reconciles(self) -> bool:
        """The invariant that makes this trustworthy: the parts sum to the
        whole, exactly."""
        total = sum(c.contribution for c in self.contributions)
        return abs((total - self.penalty_delta + self.residual) - self.delta) < 0.01

    @property
    def residual_share(self) -> float:
        """How much of the change the factors do not explain, 0–1.

        Rarely zero in practice, and that is the useful part. The trust score
        is produced by a trained model, not by the weighted sum this
        decomposition assumes — so a large share here is a real finding: the
        model scored the agent differently for reasons its input factors do
        not capture on their own. Surfacing that is the point; quietly
        distributing it across the factors would turn an honest gap into five
        small fabrications.
        """
        if self.delta == 0:
            return 0.0
        return round(min(1.0, abs(self.residual) / abs(self.delta)), 4)


def attribute_change(
    *,
    before_factors: list[dict],
    after_factors: list[dict],
    before_score: float,
    after_score: float,
    before_penalty: float = 0.0,
    after_penalty: float = 0.0,
    labels: dict[str, str] | None = None,
) -> ChangeAttribution:
    """Decompose a score change into per-factor contributions.

    Exact rather than estimated. The base score is a weighted sum, so each
    factor's share is `w_after * s_after − w_before * s_before`, and those
    terms sum to the change in the base score by construction.

    That is split further into the part from the factor's own movement and the
    part from its weight being re-tuned — because "policy compliance improved"
    and "policy compliance now counts for more" are different events, and an
    operator reading a score jump needs to know which one happened.

    A factor present on only one side is handled as a move from (or to) zero
    weight, so adding or removing a factor is attributed rather than dropped.
    """
    labels = labels or {}

    before_map = {f["key"]: f for f in before_factors}
    after_map = {f["key"]: f for f in after_factors}

    contributions: list[Contribution] = []

    for key in sorted(before_map.keys() | after_map.keys()):
        old = before_map.get(key, {})
        new = after_map.get(key, {})

        s_old = float(old.get("score", 0.0))
        s_new = float(new.get("score", 0.0))
        w_old = float(old.get("weight", 0.0))
        w_new = float(new.get("weight", 0.0))

        # w_new*s_new - w_old*s_old, split exactly:
        #   value term:  w_old * (s_new - s_old)
        #   weight term: s_new * (w_new - w_old)
        from_value = w_old * (s_new - s_old)
        from_weight = s_new * (w_new - w_old)
        total = from_value + from_weight

        # Unchanged factors are appended too, at zero. Omitting them would
        # make "this did not move" indistinguishable from "this was never
        # considered", and only one of those is reassuring.
        contributions.append(
            Contribution(
                key=key,
                label=labels.get(key, key.replace("_", " ").title()),
                before=round(s_old, 2),
                after=round(s_new, 2),
                contribution=round(total, 4),
                from_value=round(from_value, 4),
                from_weight=round(from_weight, 4),
            )
        )

    delta = round(after_score - before_score, 4)
    penalty_delta = round(after_penalty - before_penalty, 4)
    attributed = sum(c.contribution for c in contributions)

    # Everything the decomposition cannot account for, stated openly.
    residual = round(delta - (attributed - penalty_delta), 4)

    return ChangeAttribution(
        before_score=round(before_score, 2),
        after_score=round(after_score, 2),
        delta=delta,
        contributions=sorted(contributions, key=lambda c: abs(c.contribution), reverse=True),
        penalty_delta=penalty_delta,
        residual=residual,
    )
