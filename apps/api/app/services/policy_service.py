"""Database-facing orchestration around the Policy Brain.

Three responsibilities:
  - authoring: create a policy, append an immutable version, activate it
  - evaluation: run every enabled policy against a decision context
  - simulation: replay a candidate rule over stored decisions, so its blast
    radius is known *before* it governs anything
"""

from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models import Agent, Decision, Policy, PolicyVersion
from app.models.enums import DecisionOutcome
from app.services import policy_engine
from app.services.policy_engine import (
    Effect,
    PolicyContext,
    PolicyDecision,
    Rule,
    RuleEvaluation,
    RuleValidationError,
)

#: How an Effect maps onto the outcome a decision would have received.
EFFECT_TO_OUTCOME = {
    Effect.ALLOW: DecisionOutcome.APPROVED,
    Effect.REQUIRE_HUMAN_REVIEW: DecisionOutcome.ESCALATED,
    Effect.BLOCK: DecisionOutcome.BLOCKED,
}


@dataclass(frozen=True)
class PolicyEvaluationDetail:
    """One policy's evaluation, kept alongside the combined verdict so the
    console can show per-policy evidence rather than only the final effect."""

    policy_id: str
    policy_name: str
    version: str
    evaluation: RuleEvaluation


@dataclass(frozen=True)
class EvaluationResult:
    decision: PolicyDecision
    details: list[PolicyEvaluationDetail]
    #: Policies skipped because their active version's rule is unparseable.
    invalid: list[tuple[str, str]]


async def load_active_policies(db: AsyncSession) -> list[Policy]:
    """Enabled policies that have an active version, newest name order."""
    result = await db.execute(
        select(Policy)
        .options(selectinload(Policy.active_version))
        .where(Policy.enabled.is_(True))
        .order_by(Policy.name)
    )
    return [p for p in result.scalars().all() if p.active_version is not None]


def _parse_active(policy: Policy) -> Rule | None:
    """Parse a policy's active rule, or None if it is not evaluable.

    A rule that was valid when authored can become invalid later (a field
    removed from EVALUABLE_FIELDS, a hand-edited row). Returning None lets
    the caller report it explicitly instead of the policy silently never
    matching — a policy that quietly stops governing is worse than one that
    loudly fails.
    """
    if policy.active_version is None:
        return None
    try:
        return policy_engine.parse_rule(policy.active_version.rule)
    except RuleValidationError:
        return None


async def evaluate_context(db: AsyncSession, context: PolicyContext) -> EvaluationResult:
    """Run every enabled policy against one decision context."""
    policies = await load_active_policies(db)

    evaluations = []
    details = []
    invalid = []

    for policy in policies:
        rule = _parse_active(policy)
        if rule is None:
            invalid.append((policy.id, policy.name))
            continue

        evaluation = policy_engine.evaluate_rule(rule, context)
        evaluations.append((policy.id, policy.name, rule, evaluation))
        details.append(
            PolicyEvaluationDetail(
                policy_id=policy.id,
                policy_name=policy.name,
                version=policy.active_version.version if policy.active_version else "—",
                evaluation=evaluation,
            )
        )

    return EvaluationResult(
        decision=policy_engine.combine(evaluations), details=details, invalid=invalid
    )


async def context_for_decision(db: AsyncSession, decision: Decision) -> PolicyContext | None:
    """Build a PolicyContext from a stored decision and its agent."""
    agent = (
        await db.execute(select(Agent).where(Agent.id == decision.agent_id))
    ).scalar_one_or_none()
    if agent is None:
        return None

    return policy_engine.context_from_decision(
        trust_score=decision.trust_score,
        risk_score=decision.risk_score,
        amount_usd=float(decision.amount_usd) if decision.amount_usd is not None else None,
        authority_level=agent.authority_level,
        agent_lifecycle=agent.lifecycle.value,
        capability=agent.capability,
        decided_at=decision.decided_at,
    )


# --- Authoring --------------------------------------------------------------


async def create_version(
    db: AsyncSession,
    policy_id: str,
    *,
    rule: dict,
    version: str,
    note: str = "",
    created_by: str = "console",
    activate: bool = True,
) -> PolicyVersion | None:
    """Append an immutable version to a policy and optionally activate it.

    Validates the rule before writing — an unparseable rule must never
    reach storage, because by the time it is read back the author is gone
    and the failure surfaces as "this policy mysteriously governs nothing".
    """
    policy_engine.parse_rule(rule)  # raises RuleValidationError

    policy = (await db.execute(select(Policy).where(Policy.id == policy_id))).scalar_one_or_none()
    if policy is None:
        return None

    policy_version = PolicyVersion(
        policy_id=policy_id,
        version=version,
        rule=rule,
        note=note,
        created_by=created_by,
        created_at=datetime.now(UTC),
    )
    db.add(policy_version)
    await db.flush()  # assign the id before pointing the policy at it

    if activate:
        policy.active_version_id = policy_version.id
        policy.version = version

    await db.commit()
    await db.refresh(policy_version)
    return policy_version


async def load_versions(db: AsyncSession, policy_id: str) -> list[PolicyVersion]:
    result = await db.execute(
        select(PolicyVersion)
        .where(PolicyVersion.policy_id == policy_id)
        .order_by(PolicyVersion.created_at.desc())
    )
    return list(result.scalars().all())


# --- Simulation -------------------------------------------------------------


@dataclass(frozen=True)
class SimulatedDecision:
    decision_id: str
    agent_name: str
    action: str
    recorded_outcome: DecisionOutcome
    simulated_outcome: DecisionOutcome
    matched: bool
    changed: bool
    explanation: list[str]


@dataclass(frozen=True)
class RuleSimulation:
    """What a candidate rule would have done to decisions already on record."""

    evaluated: int
    matched: int
    would_block: int
    would_escalate: int
    would_allow: int
    #: Decisions where this rule's own effect differs from the recorded
    #: outcome. Read carefully: the rule is simulated alone, so an unmatched
    #: decision falls through to "allow" here even when other active policies
    #: still restrict it. A "change" from blocked to approved therefore means
    #: "this rule does not reach that case", not "this rule releases it".
    changed: list[SimulatedDecision]
    sample: list[SimulatedDecision]


async def simulate_rule(db: AsyncSession, rule_dict: dict, *, limit: int = 200) -> RuleSimulation:
    """Replay a candidate rule over stored decisions.

    This is the safety net that makes live policy editing defensible: the
    author sees exactly which historical decisions the rule catches, and
    which outcomes it would have changed, before it governs anything real.

    Evaluates the candidate rule *alone* — not combined with other active
    policies — because the question being answered is "what does this rule
    do", not "what would the whole estate do". Combining them would hide a
    dangerous rule behind an existing stricter one.
    """
    rule = policy_engine.parse_rule(rule_dict)

    result = await db.execute(select(Decision).order_by(Decision.decided_at.desc()).limit(limit))
    decisions = list(result.unique().scalars().all())

    simulated: list[SimulatedDecision] = []
    for decision in decisions:
        context = await context_for_decision(db, decision)
        if context is None:
            continue

        evaluation = policy_engine.evaluate_rule(rule, context)
        effect = evaluation.effect if evaluation.matched else Effect.ALLOW
        simulated_outcome = EFFECT_TO_OUTCOME[effect]

        simulated.append(
            SimulatedDecision(
                decision_id=decision.id,
                agent_name=decision.agent_name,
                action=decision.action,
                recorded_outcome=decision.outcome,
                simulated_outcome=simulated_outcome,
                matched=evaluation.matched,
                changed=simulated_outcome != decision.outcome,
                explanation=evaluation.explanation,
            )
        )

    return RuleSimulation(
        evaluated=len(simulated),
        matched=sum(1 for s in simulated if s.matched),
        would_block=sum(1 for s in simulated if s.simulated_outcome is DecisionOutcome.BLOCKED),
        would_escalate=sum(
            1 for s in simulated if s.simulated_outcome is DecisionOutcome.ESCALATED
        ),
        would_allow=sum(1 for s in simulated if s.simulated_outcome is DecisionOutcome.APPROVED),
        changed=[s for s in simulated if s.changed],
        sample=simulated[:20],
    )
