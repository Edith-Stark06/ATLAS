"""Capacity planning: what happens to governance if this job grows.

The question this answers is the one a bank actually asks — "we want to put
three times the volume through customer servicing, what do we need?" — and
the useful part of the answer is rarely the headline number. It is *which
constraint runs out first*, and *which agents are safe to hand the extra work
to*.

Pure functions over plain values; no database, no model loading.

**What this can and cannot say.** ATLAS observes decisions, outcomes,
policy checks and latency. From those it can project the governance
consequences of more volume: how many escalations land on humans, how many
actions get blocked, whether the latency budget still holds, and which agents
have the track record to absorb load. It knows nothing about servers, cost,
licences or queue depth, so it does not pretend to size infrastructure. The
boundary is stated in the output rather than left for the reader to discover.
"""

from dataclasses import dataclass, field

from app.services.benchmark_engine import THIN_EVIDENCE_DECISIONS

#: Minutes a human spends on one escalated decision. A parameter rather than
#: a constant of nature — it is the single biggest lever on the reviewer
#: figure, so it travels in the output as a stated assumption and can be
#: overridden by a caller who has measured their own.
DEFAULT_REVIEW_MINUTES = 12.0

#: Productive review minutes in one reviewer-day. Deliberately not 480: a
#: reviewer does not spend eight hours queue-deep, and planning as though they
#: do produces a number that fails on contact with a rota.
REVIEW_MINUTES_PER_DAY = 300.0

#: Composite benchmark score below which an agent should not be handed more
#: work. Scaling a weak agent multiplies its failures — three times the volume
#: through an agent that blocks 9% of its actions is three times the blocked
#: actions, not a capacity win.
QUALITY_FLOOR = 80.0

#: Floors on the two criteria that scaling actually multiplies, applied on top
#: of the composite.
#:
#: The composite alone is not enough, and the seeded cohort shows why: an agent
#: with the worst security and compliance in its cohort still scored 84.5,
#: because it was the fastest and speed carried it over the composite floor.
#: But speed does not offset a compliance problem — it makes the violations
#: arrive sooner. Growth is gated on the safety criteria directly.
SECURITY_FLOOR = 95.0
COMPLIANCE_FLOOR = 95.0

#: p95 latency, ms, beyond which the gate is already the slow part. Matches
#: the SLOW_MS budget the benchmark's speed criterion scores against.
LATENCY_BUDGET_MS = 2000

#: Nobody triples an agent's load overnight. Recommendations are capped at
#: this multiple of an agent's current share so the plan is one an operations
#: team could actually execute.
MAX_SHARE_GROWTH = 2.0


@dataclass(frozen=True)
class AgentCapacity:
    """What one agent contributed over the observation window."""

    agent_id: str
    agent_name: str
    decisions: int
    escalated: int
    blocked: int
    p95_latency_ms: int
    #: Composite score from the benchmark, 0–100.
    composite: float
    #: The two criteria growth multiplies, carried separately because the
    #: composite can average a safety problem away behind a speed advantage.
    security: float
    compliance: float
    thin_evidence: bool

    @property
    def fit_to_grow(self) -> bool:
        """Whether this agent can safely be handed more work."""
        return (
            not self.thin_evidence
            and self.composite >= QUALITY_FLOOR
            and self.security >= SECURITY_FLOOR
            and self.compliance >= COMPLIANCE_FLOOR
            and self.p95_latency_ms <= LATENCY_BUDGET_MS
        )


@dataclass(frozen=True)
class Constraint:
    """Something finite that more volume consumes."""

    key: str
    label: str
    #: What is available today, in the unit named.
    available: float
    #: What the target would need.
    required: float
    unit: str
    detail: str

    @property
    def headroom(self) -> float:
        """Spare capacity as a share of what is needed, 0–1.

        Negative would be misleading, so a shortfall reads as 0 and the
        `satisfied` flag carries the bad news instead.
        """
        if self.required <= 0:
            return 1.0
        return round(max(0.0, (self.available - self.required) / self.required), 4)

    @property
    def satisfied(self) -> bool:
        return self.available >= self.required

    @property
    def shortfall(self) -> float:
        return round(max(0.0, self.required - self.available), 2)


@dataclass(frozen=True)
class AgentPlan:
    agent_id: str
    agent_name: str
    #: "scale" — safe to hand more work; "hold" — keep at current share;
    #: "fix_first" — quality too low to grow; "observe" — not enough evidence.
    action: str
    current_daily: float
    recommended_daily: float
    reason: str

    @property
    def change_pct(self) -> float:
        if self.current_daily <= 0:
            return 0.0
        return round((self.recommended_daily / self.current_daily - 1) * 100, 1)


@dataclass(frozen=True)
class CapacityPlan:
    capability: str
    window_days: int
    multiplier: float

    current_daily: float
    target_daily: float

    constraints: list[Constraint] = field(default_factory=list)
    agents: list[AgentPlan] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    #: What ATLAS is not in a position to tell you. Stated rather than
    #: silently omitted, so the plan is not mistaken for a full one.
    out_of_scope: list[str] = field(default_factory=list)

    @property
    def binding(self) -> Constraint | None:
        """The constraint that runs out first.

        The whole point of the exercise: adding agents does not help when the
        thing you are short of is reviewers.
        """
        if not self.constraints:
            return None
        return min(self.constraints, key=lambda c: c.headroom)

    @property
    def feasible(self) -> bool:
        return all(c.satisfied for c in self.constraints)

    @property
    def unallocated_daily(self) -> float:
        """Target volume no agent was judged safe to take.

        Non-zero means the plan does not reach the target with the estate as
        it stands — which is a finding, not a rounding error.
        """
        planned = sum(a.recommended_daily for a in self.agents)
        return round(max(0.0, self.target_daily - planned), 2)


def _rate(count: int, total: int) -> float:
    return count / total if total else 0.0


def reviewer_days_needed(
    escalations_per_day: float, *, review_minutes: float = DEFAULT_REVIEW_MINUTES
) -> float:
    """Reviewer-days required to clear one day of escalations."""
    if escalations_per_day <= 0:
        return 0.0
    return round(escalations_per_day * review_minutes / REVIEW_MINUTES_PER_DAY, 2)


def plan_agent(
    agent: AgentCapacity,
    *,
    window_days: int,
    growth_share: float,
) -> AgentPlan:
    """Decide whether this agent should carry more of the load.

    Quality gates growth, not volume. The temptation is to scale whoever is
    already busiest, but throughput is what created the problem — the question
    is who can be trusted with more of it.
    """
    current_daily = round(agent.decisions / window_days, 2)

    if agent.thin_evidence:
        return AgentPlan(
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            action="observe",
            current_daily=current_daily,
            recommended_daily=current_daily,
            reason=(
                f"only {agent.decisions} decision{'' if agent.decisions == 1 else 's'} "
                f"on record — too few to plan capacity on. Needs "
                f"{THIN_EVIDENCE_DECISIONS}+ before its rates mean anything."
            ),
        )

    failing = []
    if agent.composite < QUALITY_FLOOR:
        failing.append(f"scores {agent.composite:.0f} against a {QUALITY_FLOOR:.0f} floor")
    if agent.security < SECURITY_FLOOR:
        failing.append(f"security {agent.security:.0f} against a {SECURITY_FLOOR:.0f} floor")
    if agent.compliance < COMPLIANCE_FLOOR:
        failing.append(f"compliance {agent.compliance:.0f} against a {COMPLIANCE_FLOOR:.0f} floor")

    if failing:
        blocked_rate = _rate(agent.blocked, agent.decisions)
        return AgentPlan(
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            action="fix_first",
            current_daily=current_daily,
            recommended_daily=current_daily,
            reason=(
                f"{'; '.join(failing)} — {blocked_rate:.0%} of its actions are blocked. "
                "More volume here multiplies the failures rather than adding capacity, "
                "and being fast does not offset that."
            ),
        )

    if agent.p95_latency_ms > LATENCY_BUDGET_MS:
        return AgentPlan(
            agent_id=agent.agent_id,
            agent_name=agent.agent_name,
            action="hold",
            current_daily=current_daily,
            recommended_daily=current_daily,
            reason=(
                f"p95 already {agent.p95_latency_ms}ms, past the "
                f"{LATENCY_BUDGET_MS}ms budget. Adding load makes the tail worse."
            ),
        )

    recommended = round(min(current_daily * MAX_SHARE_GROWTH, growth_share), 2)
    return AgentPlan(
        agent_id=agent.agent_id,
        agent_name=agent.agent_name,
        action="scale" if recommended > current_daily else "hold",
        current_daily=current_daily,
        recommended_daily=max(recommended, current_daily),
        reason=(
            f"scores {agent.composite:.0f} with {agent.decisions} decisions behind it — "
            f"capped at {MAX_SHARE_GROWTH:.0f}× its current share, which is what an "
            "operations team can actually stand up."
        ),
    )


def build_plan(
    *,
    capability: str,
    cohort: list[AgentCapacity],
    window_days: int,
    multiplier: float,
    reviewer_days_available: float,
    review_minutes: float = DEFAULT_REVIEW_MINUTES,
) -> CapacityPlan:
    """Project the governance consequences of growing this job."""
    window_days = max(1, window_days)
    multiplier = max(1.0, multiplier)

    total_decisions = sum(a.decisions for a in cohort)
    total_escalated = sum(a.escalated for a in cohort)
    total_blocked = sum(a.blocked for a in cohort)

    current_daily = round(total_decisions / window_days, 2)
    target_daily = round(current_daily * multiplier, 2)

    escalation_rate = _rate(total_escalated, total_decisions)
    block_rate = _rate(total_blocked, total_decisions)

    # --- constraints -------------------------------------------------------

    target_escalations = target_daily * escalation_rate
    reviewers_required = reviewer_days_needed(target_escalations, review_minutes=review_minutes)

    constraints = [
        Constraint(
            key="human_review",
            label="Human review",
            available=round(reviewer_days_available, 2),
            required=reviewers_required,
            unit="reviewer-days/day",
            detail=(
                f"{escalation_rate:.1%} of actions escalate. At {target_daily:,.0f} "
                f"decisions/day that is {target_escalations:,.0f} escalations, "
                f"{review_minutes:.0f} minutes each."
            ),
        )
    ]

    # Capacity the estate can safely absorb, given who is fit to grow.
    healthy = [a for a in cohort if a.fit_to_grow]
    safe_daily = round(sum(a.decisions / window_days for a in healthy) * MAX_SHARE_GROWTH, 2)

    constraints.append(
        Constraint(
            key="trusted_throughput",
            label="Trusted agent capacity",
            available=safe_daily,
            required=target_daily,
            unit="decisions/day",
            detail=(
                f"{len(healthy)} of {len(cohort)} agents are fit to grow (clearing the "
                f"composite, security and compliance floors, and inside the latency "
                f"budget), each capped at {MAX_SHARE_GROWTH:.0f}× its current share."
            ),
        )
    )

    # Measured across the agents that would actually receive load, not the
    # whole cohort. A slow agent that is being held is not a scaling
    # constraint — blocking growth on it would let one agent nobody is
    # touching veto the entire plan, which is how a constraint becomes noise.
    slowest = max((a.p95_latency_ms for a in healthy), default=0)
    constraints.append(
        Constraint(
            key="latency_budget",
            label="Latency budget",
            available=float(LATENCY_BUDGET_MS),
            required=float(slowest),
            unit="ms (p95)",
            detail=(
                f"slowest agent taking extra load sits at {slowest}ms p95. Load makes "
                "tails worse, so an agent already near the budget has no room."
            ),
        )
    )

    # --- per-agent allocation ----------------------------------------------

    # Share the target across agents fit to take it, weighted by quality: the
    # best agent earns the largest slice rather than everyone growing equally.
    # Matched on id rather than dataclass equality: two agents with identical
    # metrics are still two agents, and value equality would conflate them.
    healthy_ids = {a.agent_id for a in healthy}
    quality_total = sum(a.composite for a in healthy) or 1.0

    plans = [
        plan_agent(
            agent,
            window_days=window_days,
            growth_share=(
                target_daily * (agent.composite / quality_total)
                if agent.agent_id in healthy_ids
                else 0.0
            ),
        )
        for agent in cohort
    ]

    # Worst first — the reader wants the problems, not a leaderboard.
    order = {"fix_first": 0, "hold": 1, "observe": 2, "scale": 3}
    plans.sort(key=lambda p: (order.get(p.action, 9), -p.recommended_daily))

    return CapacityPlan(
        capability=capability,
        window_days=window_days,
        multiplier=multiplier,
        current_daily=current_daily,
        target_daily=target_daily,
        constraints=constraints,
        agents=plans,
        assumptions=[
            f"{review_minutes:.0f} minutes of human time per escalated decision.",
            f"{REVIEW_MINUTES_PER_DAY:.0f} productive review minutes per reviewer-day.",
            (
                f"Escalation ({escalation_rate:.1%}) and block ({block_rate:.1%}) rates "
                "hold at the higher volume. They are measured at today's load, and "
                "rates observed under light load do not always survive heavy load."
            ),
            f"No agent grows beyond {MAX_SHARE_GROWTH:.0f}× its current share.",
        ],
        out_of_scope=[
            "Infrastructure sizing — ATLAS observes decisions, not servers, "
            "queue depth or licence limits.",
            "Cost. Reviewer-days are an effort figure, not a budget.",
            "Whether the extra demand exists. This projects what governance "
            "would need, not what the business will actually receive.",
        ],
    )
