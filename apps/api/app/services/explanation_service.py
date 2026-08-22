"""Assembles an explanation for a decision that actually happened.

The engine does the reasoning; this fetches the evidence and, crucially,
reconstructs the *conditions at decision time* rather than re-deriving them
from today's state.

That distinction is the whole point. Re-evaluating a six-month-old decision
against the current policy set and a retrained model would produce a coherent,
confident, and wrong explanation — one describing a decision the system never
made. The governance ledger already pins what was in force; this reads it.
"""

import math
from dataclasses import dataclass, replace
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ml import models as ml_models
from app.models import Decision, LedgerEntry
from app.models.enums import DecisionOutcome
from app.services import explanation_engine, ledger_service, policy_service, trust_service
from app.services.explanation_engine import (
    Counterfactual,
    Driver,
    Explanation,
    RuleEvidence,
)
from app.services.policy_engine import Effect

FACTOR_LABELS = {
    "behavior": "Behavior Consistency",
    "policy": "Policy Compliance",
    "risk": "Risk Exposure",
    "context": "Context Awareness",
    "history": "Historical Reliability",
}

#: Outcomes the model has to clear for an action to run.
RESTRICTIVE_EFFECTS = (Effect.BLOCK, Effect.REQUIRE_HUMAN_REVIEW)


class DecisionNotFound(LookupError):
    pass


@dataclass(frozen=True)
class DecisionExplanation:
    decision_id: str
    agent_id: str
    agent_name: str
    action: str
    explanation: Explanation
    #: Ledger position this was reconstructed from, when one exists. Its
    #: absence is reported rather than hidden: an explanation with no audit
    #: record behind it is a weaker claim, and the reader should know.
    ledger_seq: int | None
    #: True when the rule versions and model came from the pinned record
    #: rather than from current state.
    from_pinned_evidence: bool


async def _ledger_entry_for(db: AsyncSession, decision_id: str) -> LedgerEntry | None:
    entries = await ledger_service.list_entries(db, limit=1, subject_id=decision_id)
    return entries[0] if entries else None


def _rules_from_payload(payload: dict[str, Any]) -> list[RuleEvidence]:
    """Rule evidence exactly as recorded, versions included."""
    evaluated = payload.get("policy", {}).get("evaluated", [])
    return [
        RuleEvidence(
            policy_id=rule.get("policyId", ""),
            policy_name=rule.get("policyName", ""),
            version=rule.get("version", ""),
            matched=bool(rule.get("matched")),
            in_scope=bool(rule.get("inScope")),
            effect=Effect(rule["effect"]) if rule.get("effect") else None,
            conditions=[],
        )
        for rule in evaluated
    ]


def _simulation_features(payload: dict[str, Any]) -> dict[str, float] | None:
    """Rebuild the classifier's input from the pinned record.

    Returns None when the record predates a field the model needs — better to
    offer no model counterfactual than one computed from a guessed input.
    """
    inputs = payload.get("inputs") or {}
    decision = payload.get("decision") or {}

    risk = inputs.get("riskScore")
    trust = inputs.get("trustScore")
    hour = inputs.get("hourUtc")
    if risk is None or trust is None or hour is None:
        return None

    amount_raw = decision.get("amountUsd")
    amount = float(amount_raw) if amount_raw is not None else 0.0

    return {
        "risk_score": float(risk),
        "log_amount": math.log1p(amount),
        "hour": float(hour),
        "policy_pass_rate": 1.0,
        "trust_proxy": float(trust),
        "authority_level": 2.0,
        # Kept alongside so the counterfactual search can vary it directly;
        # log_amount is recomputed from it on each probe.
        "amount_usd": amount,
    }


def _model_predictor():
    """A predict function over the searchable feature space, or None.

    `amount_usd` is the axis an operator can actually act on, but the model
    consumes `log_amount`; the wrapper keeps them consistent so a probe cannot
    silently vary one without the other.
    """
    model = ml_models.load_simulation_model()
    if model is None:
        return None

    def predict(features: dict[str, float]) -> DecisionOutcome:
        probe = dict(features)
        if "amount_usd" in probe:
            probe["log_amount"] = math.log1p(max(0.0, probe["amount_usd"]))
        predictions = model.predict_outcomes(probe)
        best = max(predictions, key=lambda p: p["probability"])
        return DecisionOutcome(best["outcome"])

    return predict


async def explain_decision(db: AsyncSession, decision_id: str) -> DecisionExplanation:
    """Explain a stored decision from its pinned evidence."""
    decision = (
        (await db.execute(select(Decision).where(Decision.id == decision_id)))
        .unique()
        .scalar_one_or_none()
    )
    if decision is None:
        raise DecisionNotFound(f"Decision '{decision_id}' not found")

    entry = await _ledger_entry_for(db, decision_id)
    payload = entry.payload if entry else {}
    agent_name = decision.agent_name or "Unknown agent"

    policy_forced = bool(payload.get("policy", {}).get("forced"))
    decided_by = "policy" if policy_forced else "model"

    narrative = [decision.rationale] if decision.rationale else []
    rules = _rules_from_payload(payload)

    counterfactuals: list[Counterfactual] = []

    # --- policy side: exact, and only meaningful when a rule was binding ---
    if policy_forced:
        binding = [r for r in rules if r.matched and r.effect in RESTRICTIVE_EFFECTS]
        counterfactuals.extend(await _policy_counterfactuals(db, binding, decision))
        if binding:
            names = ", ".join(f"{r.policy_name} {r.version}" for r in binding)
            narrative.append(f"Binding rule(s): {names}.")

    # --- model side: searched, and only when the model was the decider ---
    elif decision.outcome is not DecisionOutcome.APPROVED:
        features = _simulation_features(payload)
        predict = _model_predictor()
        if features is not None and predict is not None:
            counterfactuals.extend(
                explanation_engine.model_counterfactuals(
                    features=features,
                    predict=predict,
                    current_outcome=decision.outcome,
                )
            )

    drivers = await _drivers_for(db, decision.agent_id)

    explanation = Explanation(
        outcome=decision.outcome,
        headline=explanation_engine.headline(decision.outcome, decided_by, agent_name),
        decided_by=decided_by,
        narrative=narrative,
        drivers=drivers,
        rules=rules,
        counterfactuals=counterfactuals,
    )

    return DecisionExplanation(
        decision_id=decision.id,
        agent_id=decision.agent_id,
        agent_name=agent_name,
        action=decision.action,
        explanation=explanation,
        ledger_seq=entry.seq if entry else None,
        from_pinned_evidence=entry is not None,
    )


async def _policy_counterfactuals(
    db: AsyncSession, binding: list[RuleEvidence], decision: Decision
) -> list[Counterfactual]:
    """Exact boundaries, computed against the rule version that was in force.

    The stored payload records *that* a rule matched, not the individual
    conditions, so the versioned rule text is loaded to recover them — the
    pinned version string is what makes that safe to do after the fact.
    """
    if not binding:
        return []

    context = await policy_service.context_for_decision(db, decision)
    if context is None:
        return []

    candidates: list[Counterfactual] = []
    for evidence in binding:
        rule = await policy_service.load_rule_version(db, evidence.policy_id, evidence.version)
        if rule is None:
            continue
        evaluation = policy_service.policy_engine.evaluate_rule(rule, context)
        pairs = [(result.condition, result) for result in evaluation.results]
        candidates.extend(explanation_engine.policy_counterfactuals(pairs))

    return await _verified(db, candidates, context, decision.outcome)


async def _verified(
    db: AsyncSession,
    candidates: list[Counterfactual],
    context: "policy_service.PolicyContext",
    current: DecisionOutcome,
) -> list[Counterfactual]:
    """Keep only the changes that actually change the verdict.

    A boundary is computed per rule, but the verdict comes from the whole
    active set. When two rules bind, clearing one leaves the other in force —
    so "amount at most $2,000" can be exactly right about its own rule and
    completely wrong as advice, because the sanctions rule still blocks.

    Each candidate is therefore replayed against every rule and kept only if
    the combined effect improves. `changes_to` is set to what the outcome
    actually becomes, which is not always approval: clearing a block can still
    leave a review requirement behind.
    """
    verified: list[Counterfactual] = []

    for candidate in candidates:
        probe = replace(context, **{candidate.field: candidate.threshold})
        result = await policy_service.evaluate_context(db, probe)
        outcome = policy_service.EFFECT_TO_OUTCOME[result.decision.effect]

        if outcome is current:
            continue

        verified.append(
            replace(
                candidate,
                changes_to=outcome,
                detail=(
                    f"{candidate.label} {candidate.direction} "
                    f"{_display(candidate.field, candidate.threshold)} "
                    f"changes this to {outcome.value}"
                ),
            )
        )

    return verified


def _display(field_name: str, value: float) -> str:
    if field_name == "amount_usd":
        return f"${value:,.2f}"
    return str(int(value)) if float(value).is_integer() else f"{value:,.2f}"


async def _drivers_for(db: AsyncSession, agent_id: str) -> list[Driver]:
    """Trust attribution for the agent.

    Current rather than historical: trust factor history is snapshotted, but
    per-factor SHAP attribution is not, so this is the agent's standing today.
    Labelled as such in the API response rather than passed off as the
    attribution at decision time.
    """
    loaded = await trust_service.evaluate_agent(db, agent_id)
    if loaded is None:
        return []

    agent, evaluation, _snapshots, _anomaly = loaded
    factors = {factor.key: float(factor.score) for factor in agent.factors}

    return explanation_engine.drivers_from_attribution(
        evaluation.ml_attribution, factors=factors, labels=FACTOR_LABELS
    )
