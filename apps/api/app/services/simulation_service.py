"""Database-facing orchestration around the Simulation Engine.

Runs the full pre-execution evaluation for a proposed action: look up the
agent's trust, evaluate the active policy set, predict outcome
probabilities with the trained classifier, and reduce all three to one
recommendation — optionally persisting the run for audit.
"""

import math
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.ml import models as ml_models
from app.models import Agent, SimulationOutcome, SimulationRun
from app.models.enums import DecisionOutcome
from app.services import policy_engine, policy_service, simulation_engine
from app.services.policy_engine import Effect
from app.services.simulation_engine import SimulationVerdict

#: Probabilities used when no trained classifier is on disk. Deliberately
#: uninformative — an even split says "no signal", which is honest, rather
#: than a confident guess the system has not earned.
UNTRAINED_FALLBACK = dict.fromkeys(DecisionOutcome, 1 / 3)


@dataclass(frozen=True)
class SimulationRequest:
    agent_id: str | None
    action: str
    amount_usd: float | None
    risk_score: int
    #: Overrides the agent's stored trust score when set — this is what makes
    #: "what if this agent's trust dropped to 40?" answerable.
    trust_score: int | None = None
    hour_utc: int | None = None
    policy_pass_rate: float = 1.0


@dataclass(frozen=True)
class SimulationResult:
    verdict: SimulationVerdict
    agent_id: str | None
    agent_name: str
    trust_score: int
    capability: str
    policy_effect: Effect
    policy_evaluations: list[policy_service.PolicyEvaluationDetail]
    #: True when the outcome probabilities came from the trained model rather
    #: than the uninformative fallback.
    model_backed: bool
    duration_ms: int
    #: Set when the run was persisted.
    run_id: str | None = None


class AgentNotFound(LookupError):
    """Raised when a simulation names an agent that does not exist."""

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"Agent '{agent_id}' not found")
        self.agent_id = agent_id


async def _load_agent(db: AsyncSession, agent_id: str | None) -> Agent | None:
    """The named agent, or None for a deliberately unattributed scenario.

    A missing agent is an error rather than a fallback: silently scoring a
    typo'd ID against default trust would hand back a confident verdict for
    an agent nobody evaluated, which is the exact failure this system exists
    to prevent.
    """
    if agent_id is None:
        return None
    result = await db.execute(
        select(Agent).options(selectinload(Agent.factors)).where(Agent.id == agent_id)
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise AgentNotFound(agent_id)
    return agent


def _predict(request: SimulationRequest, trust_score: int) -> tuple[dict, bool]:
    """Outcome probabilities from the trained classifier, or an even split."""
    model = ml_models.load_simulation_model()
    if model is None:
        return dict(UNTRAINED_FALLBACK), False

    predictions = model.predict_outcomes(
        {
            "risk_score": request.risk_score,
            "log_amount": math.log1p(request.amount_usd or 0.0),
            "hour": request.hour_utc if request.hour_utc is not None else 12,
            "policy_pass_rate": request.policy_pass_rate,
            "trust_proxy": trust_score,
            "authority_level": 2,
        }
    )
    probabilities = {DecisionOutcome(p["outcome"]): p["probability"] for p in predictions}
    return probabilities, True


async def run(
    db: AsyncSession, request: SimulationRequest, *, persist_for_decision: str | None = None
) -> SimulationResult:
    """Evaluate a proposed action end to end.

    `persist_for_decision` writes a SimulationRun against an existing
    decision. Left None, nothing is stored — the common case is a what-if
    from the console, which should not pollute the audit trail.
    """
    started = time.perf_counter()

    agent = await _load_agent(db, request.agent_id)
    trust_score = (
        request.trust_score
        if request.trust_score is not None
        else (agent.trust_score if agent else 50)
    )
    capability = agent.capability if agent else ""
    lifecycle = agent.lifecycle.value if agent else "healthy"
    authority = agent.authority_level if agent else 2

    context = policy_engine.PolicyContext(
        trust_score=trust_score,
        risk_score=request.risk_score,
        amount_usd=request.amount_usd,
        authority_level=authority,
        agent_lifecycle=lifecycle,
        capability=capability,
        hour_utc=request.hour_utc if request.hour_utc is not None else 12,
    )
    policy_result = await policy_service.evaluate_context(db, context)

    probabilities, model_backed = _predict(request, trust_score)
    verdict = simulation_engine.simulate(
        probabilities=probabilities,
        policy_effect=policy_result.decision.effect,
        amount_usd=request.amount_usd,
        risk_score=request.risk_score,
    )

    duration_ms = max(1, int((time.perf_counter() - started) * 1000))

    run_id = None
    if persist_for_decision is not None:
        run_id = await _persist(
            db,
            decision_id=persist_for_decision,
            request=request,
            verdict=verdict,
            agent_name=agent.name if agent else "Ad-hoc scenario",
            trust_score=trust_score,
            duration_ms=duration_ms,
        )

    return SimulationResult(
        verdict=verdict,
        agent_id=request.agent_id,
        agent_name=agent.name if agent else "Ad-hoc scenario",
        trust_score=trust_score,
        capability=capability,
        policy_effect=policy_result.decision.effect,
        policy_evaluations=policy_result.details,
        model_backed=model_backed,
        duration_ms=duration_ms,
        run_id=run_id,
    )


async def _persist(
    db: AsyncSession,
    *,
    decision_id: str,
    request: SimulationRequest,
    verdict: SimulationVerdict,
    agent_name: str,
    trust_score: int,
    duration_ms: int,
) -> str:
    run_id = f"sim-{uuid.uuid4().hex[:12]}"

    db.add(
        SimulationRun(
            id=run_id,
            decision_id=decision_id,
            scenario=request.action,
            agent_name=agent_name,
            amount_usd=(
                Decimal(str(request.amount_usd)) if request.amount_usd is not None else None
            ),
            trust_score=trust_score,
            confidence=verdict.confidence,
            recommendation=verdict.recommendation,
            ran_at=datetime.now(UTC),
            duration_ms=duration_ms,
            request=build_request_rows(request, trust_score, agent_name),
        )
    )
    await db.flush()

    for outcome in verdict.outcomes:
        db.add(
            SimulationOutcome(
                run_id=run_id,
                label=outcome.label,
                probability=outcome.probability,
                financial_impact_usd=Decimal(str(outcome.financial_impact_usd)),
                risk_score=outcome.risk_score,
                compliant=outcome.compliant,
                recommended=outcome.recommended,
            )
        )

    # Flush, never commit: the decision pipeline writes the decision, its
    # policy checks, this run and the ledger entry as one unit. A commit here
    # would let a decision exist without its audit record.
    await db.flush()
    return run_id


async def attach_to_decision(
    db: AsyncSession,
    *,
    decision_id: str,
    request: SimulationRequest,
    result: SimulationResult,
) -> str:
    """Store an already-computed verdict against a decision.

    The pipeline needs the verdict *before* the decision row exists (it is
    what determines the outcome), so it cannot use `run(persist_for_decision=)`.
    Re-running the model afterwards would risk persisting a prediction subtly
    different from the one that actually decided.
    """
    return await _persist(
        db,
        decision_id=decision_id,
        request=request,
        verdict=result.verdict,
        agent_name=result.agent_name,
        trust_score=result.trust_score,
        duration_ms=result.duration_ms,
    )


def build_request_rows(request: SimulationRequest, trust_score: int, agent_name: str) -> list[dict]:
    """The label/value rows the console renders as "Incoming Request"."""
    rows = [
        {"label": "Agent", "value": agent_name},
        {"label": "Action", "value": request.action},
    ]
    if request.amount_usd is not None:
        rows.append({"label": "Amount", "value": f"${request.amount_usd:,.2f}"})
    rows.append({"label": "Risk Score", "value": f"{request.risk_score} / 100"})
    rows.append({"label": "Current Trust", "value": f"{trust_score} / 100"})
    if request.hour_utc is not None:
        rows.append({"label": "Hour (UTC)", "value": f"{request.hour_utc:02d}:00"})
    return rows


async def rebuild_for_decisions(db: AsyncSession) -> int:
    """Regenerate every stored simulation from the current engine.

    The seeded runs shipped with hand-written outcome percentages. This
    replaces them with model-backed predictions so what the console shows is
    something the system actually computed.
    """
    from app.models import Decision

    decisions = list(
        (await db.execute(select(Decision).order_by(Decision.decided_at.desc())))
        .unique()
        .scalars()
        .all()
    )

    # Clear existing runs; outcomes cascade.
    for existing in (await db.execute(select(SimulationRun))).scalars().all():
        await db.delete(existing)
    await db.flush()

    rebuilt = 0
    for decision in decisions:
        request = SimulationRequest(
            agent_id=decision.agent_id,
            action=decision.action,
            amount_usd=(float(decision.amount_usd) if decision.amount_usd is not None else None),
            risk_score=decision.risk_score,
            trust_score=decision.trust_score,
            hour_utc=decision.decided_at.hour,
        )
        await run(db, request, persist_for_decision=decision.id)
        rebuilt += 1

    # One commit for the whole rebuild — a failure part-way through leaves the
    # previous runs intact rather than a half-regenerated ledger view.
    await db.commit()
    return rebuilt
