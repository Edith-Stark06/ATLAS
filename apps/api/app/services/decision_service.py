"""The decision pipeline: the path an agent's action actually takes.

Everything before this phase evaluated hypotheticals. This is the committing
path — it runs the same pre-execution evaluation, then records what was
decided, why, and against which rules and model.

Order matters and is not arbitrary. Trust and policy and simulation all run
*before* anything is written, so a request that is going to be blocked is
blocked on evidence gathered before the block, not justified after it. The
ledger entry is appended in the same transaction as the decision: a decision
that exists without an audit record is precisely the failure this system is
built to prevent.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Agent, Decision, LedgerEntry, PolicyCheck
from app.models.enums import DecisionOutcome
from app.services import ledger, ledger_service, simulation_service
from app.services.policy_engine import Effect
from app.services.simulation_service import SimulationRequest, SimulationResult

#: Outcomes that mean the action does not run. Kept explicit rather than
#: `!= APPROVED` so adding a fourth outcome forces a decision here.
NON_EXECUTING = frozenset({DecisionOutcome.ESCALATED, DecisionOutcome.BLOCKED})


class AgentNotFound(LookupError):
    """Re-exported so callers of the pipeline need only catch one error type."""


class DuplicateDecision(ValueError):
    """A decision already exists under the caller's reference.

    Enterprise systems retry on timeout, so the same transaction id will
    arrive twice. Recording a second decision would double-count the action
    and put two conflicting verdicts in the audit trail for one event;
    crashing with a database error tells the caller nothing. Refusing
    explicitly lets them fetch what was already decided.
    """

    def __init__(self, decision_id: str) -> None:
        super().__init__(f"Decision '{decision_id}' already exists")
        self.decision_id = decision_id


@dataclass(frozen=True)
class ExecuteRequest:
    agent_id: str
    action: str
    amount_usd: float | None = None
    risk_score: int = 20
    hour_utc: int | None = None
    #: Reference from the originating enterprise system. Generated when absent.
    decision_id: str | None = None


@dataclass(frozen=True)
class ExecuteResult:
    decision: Decision
    simulation: SimulationResult
    ledger_entry: LedgerEntry
    #: True when the action is cleared to run. The caller is the thing that
    #: would actually move money, so it needs this as a plain boolean rather
    #: than having to re-derive it from the outcome.
    executed: bool


#: Money is stored in a Numeric(16, 2) column, so it must reach the ledger in
#: that same shape. Hashing `str(Decimal("12450.5"))` would pin "12450.5"
#: against a database that holds 12450.50 — the same amount with two
#: spellings, which is exactly the ambiguity the chain is supposed to remove.
CENTS = Decimal("0.01")


def _money(amount: float | None) -> Decimal | None:
    """Round to cents once, up front, using the rounding a finance team
    expects rather than Python's banker's default."""
    if amount is None:
        return None
    return Decimal(str(amount)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _new_decision_id() -> str:
    """Matches the seeded `TRX-XXXX` shape, with enough width that collisions
    are not a practical concern."""
    return f"TRX-{uuid.uuid4().hex[:8].upper()}"


def _rationale(result: SimulationResult) -> str:
    """One sentence an auditor can read without opening the payload."""
    return " ".join(result.verdict.explanation)


def _policy_checks(decision_id: str, result: SimulationResult) -> list[PolicyCheck]:
    """One row per policy evaluated, pass or fail.

    Recording only the failures would make a clean decision indistinguishable
    from one where nothing was checked.
    """
    checks = []
    for detail in result.policy_evaluations:
        evaluation = detail.evaluation
        restricted = evaluation.matched and evaluation.effect in (
            Effect.BLOCK,
            Effect.REQUIRE_HUMAN_REVIEW,
        )
        if not evaluation.in_scope:
            note = "Out of scope for this agent's capability"
        elif not evaluation.matched:
            note = "Conditions not met"
        else:
            note = f"Matched — effect: {evaluation.effect.value if evaluation.effect else 'allow'}"

        checks.append(
            PolicyCheck(
                decision_id=decision_id,
                policy_id=detail.policy_id,
                policy_name=detail.policy_name,
                passed=not restricted,
                detail=note[:300],
            )
        )
    return checks


def _ledger_payload(
    *,
    decision: Decision,
    result: SimulationResult,
    request: SimulationRequest,
) -> dict:
    """The evidence pinned into the hash.

    This is the record an auditor recomputes against, so it holds everything
    needed to explain the verdict without trusting the rest of the database:
    the inputs, the rule *versions* in force at the time, the model that
    scored it, and what the decision cost. Amounts are strings because
    hashing a float would make the record depend on repr precision.

    `request` is the *resolved* evaluation request, not the caller's raw one.
    Defaults are filled in by then, so recording an omitted hour as `null`
    here would pin an input the engine never actually used — and a decision
    an auditor cannot reproduce is not evidence of anything.
    """
    verdict = result.verdict
    return {
        "decision": {
            "id": decision.id,
            "agentId": decision.agent_id,
            "agentName": result.agent_name,
            "action": decision.action,
            "amountUsd": None if decision.amount_usd is None else str(decision.amount_usd),
            "outcome": decision.outcome.value,
            "decidedAt": ledger.iso(decision.decided_at),
            "latencyMs": decision.latency_ms,
        },
        "inputs": {
            "trustScore": result.trust_score,
            "riskScore": request.risk_score,
            "capability": result.capability,
            "hourUtc": request.hour_utc,
        },
        "policy": {
            "effect": result.policy_effect.value,
            "forced": verdict.policy_forced,
            # Versions, not just ids: a policy renamed or re-authored later
            # must not change what this decision is judged against.
            "evaluated": [
                {
                    "policyId": detail.policy_id,
                    "policyName": detail.policy_name,
                    "version": detail.version,
                    "matched": detail.evaluation.matched,
                    "inScope": detail.evaluation.in_scope,
                    "effect": (
                        detail.evaluation.effect.value if detail.evaluation.effect else None
                    ),
                }
                for detail in result.policy_evaluations
            ],
        },
        "model": {
            "backed": result.model_backed,
            "fingerprint": ledger_service.model_fingerprint(),
        },
        "prediction": {
            "recommendation": verdict.recommendation.value,
            "confidence": verdict.confidence,
            "adverseProbability": verdict.adverse_probability,
            "outcomes": [
                {"outcome": o.outcome.value, "probability": o.probability} for o in verdict.outcomes
            ],
        },
        "exposure": {
            "expectedUsd": f"{verdict.expected_exposure_usd:.2f}",
            "withheldUsd": f"{verdict.withheld_usd:.2f}",
            "unconstrainedUsd": f"{verdict.unconstrained_exposure_usd:.2f}",
        },
    }


async def execute(db: AsyncSession, request: ExecuteRequest) -> ExecuteResult:
    """Run an action through the pipeline and commit the outcome.

    Raises AgentNotFound if the agent does not exist — an unknown agent must
    not be governed against default trust.
    """
    decided_at = datetime.now(UTC)
    evaluation_request = SimulationRequest(
        agent_id=request.agent_id,
        action=request.action,
        amount_usd=request.amount_usd,
        risk_score=request.risk_score,
        hour_utc=request.hour_utc if request.hour_utc is not None else decided_at.hour,
    )

    try:
        result = await simulation_service.run(db, evaluation_request)
    except simulation_service.AgentNotFound as exc:
        raise AgentNotFound(str(exc)) from exc

    outcome = result.verdict.recommendation
    decision_id = request.decision_id or _new_decision_id()

    if request.decision_id is not None and await db.get(Decision, decision_id) is not None:
        raise DuplicateDecision(decision_id)

    decision = Decision(
        id=decision_id,
        agent_id=request.agent_id,
        action=request.action,
        amount_usd=_money(request.amount_usd),
        outcome=outcome,
        trust_score=result.trust_score,
        risk_score=request.risk_score,
        decided_at=decided_at,
        latency_ms=result.duration_ms,
        rationale=_rationale(result),
        investigation=None,
    )
    db.add(decision)
    await db.flush()

    for check in _policy_checks(decision_id, result):
        db.add(check)

    # Store the verdict that actually decided this, not a fresh one — the
    # decision detail view must show the prediction the system acted on.
    await simulation_service.attach_to_decision(
        db, decision_id=decision_id, request=evaluation_request, result=result
    )

    agent = await db.get(Agent, request.agent_id)
    if agent is not None:
        agent.decisions_today += 1
        agent.last_active_at = decided_at
        agent.last_decision = request.action[:300]

    entry = await ledger_service.append(
        db,
        kind=ledger.LedgerKind.DECISION_RECORDED,
        subject_id=decision_id,
        payload=_ledger_payload(decision=decision, result=result, request=evaluation_request),
        recorded_at=decided_at,
    )

    # One commit for the decision, its policy checks, its simulation and its
    # ledger entry. Either all of it is on the record or none of it is.
    await db.commit()
    return ExecuteResult(
        decision=decision,
        simulation=result,
        ledger_entry=entry,
        executed=outcome not in NON_EXECUTING,
    )
