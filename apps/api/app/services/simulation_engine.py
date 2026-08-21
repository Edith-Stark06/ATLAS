"""The Simulation Engine.

Answers "what happens if we allow this?" *before* the action executes, by
combining three inputs that already exist independently:

  - the agent's trust score          (Trust Engine)
  - the verdict of the active rules  (Policy Brain)
  - predicted outcome probabilities  (trained classifier, app.ml)

and reducing them to one recommendation plus the financial exposure that
recommendation implies.

Pure functions over plain values — no database, no model loading. The
service layer (app/services/simulation_service.py) supplies the inputs.
"""

from dataclasses import dataclass, field

from app.models.enums import DecisionOutcome
from app.services.policy_engine import Effect

#: Human-readable name for each predicted future.
OUTCOME_LABELS = {
    DecisionOutcome.APPROVED: "Executes as requested",
    DecisionOutcome.ESCALATED: "Held for human review",
    DecisionOutcome.BLOCKED: "Blocked before execution",
}

#: Share of the assessed risk that actually lands, per path.
#:
#: These are *stated modelling assumptions*, not measured mitigation rates:
#: approving takes the full assessed risk, a human review is assumed to catch
#: most of it, and an action that never runs carries none. They are declared
#: here rather than buried in a formula so the assumption can be argued with.
RESIDUAL_RISK_FACTOR = {
    DecisionOutcome.APPROVED: 1.0,
    DecisionOutcome.ESCALATED: 0.35,
    DecisionOutcome.BLOCKED: 0.0,
}

#: Combined probability of an adverse path above which the engine escalates
#: even when the rules permit the action — the model is seeing risk the
#: policy set does not encode.
ADVERSE_ESCALATION_THRESHOLD = 0.45

#: How an Effect maps onto the outcome it forces.
EFFECT_TO_OUTCOME = {
    Effect.ALLOW: DecisionOutcome.APPROVED,
    Effect.REQUIRE_HUMAN_REVIEW: DecisionOutcome.ESCALATED,
    Effect.BLOCK: DecisionOutcome.BLOCKED,
}


@dataclass(frozen=True)
class PredictedOutcome:
    outcome: DecisionOutcome
    label: str
    #: 0–1, from the trained classifier.
    probability: float
    #: Money that moves down this path. Zero where the action never runs.
    financial_impact_usd: float
    #: Residual risk if this path is taken, 0–100.
    risk_score: int
    #: Whether this path is consistent with what the rules permit.
    compliant: bool
    recommended: bool = False


@dataclass(frozen=True)
class SimulationVerdict:
    recommendation: DecisionOutcome
    outcomes: list[PredictedOutcome]
    #: Confidence in the recommended path, 0–100.
    confidence: float
    #: Money that moves if the recommendation is followed. Deterministic, not
    #: probability-weighted: once the recommendation is to block or escalate,
    #: nothing moves — reporting a weighted figure there would quote an
    #: exposure the system is actively preventing.
    expected_exposure_usd: float
    #: Amount held back by following the recommendation.
    withheld_usd: float
    #: What an unpoliced system would expose on average, i.e. the amount
    #: weighted by the model's approval probability. The gap between this and
    #: expected_exposure_usd is what the governance layer is buying.
    unconstrained_exposure_usd: float
    #: Combined probability of a non-approval path.
    adverse_probability: float
    #: Whether the rules, not the model, determined the recommendation.
    policy_forced: bool
    explanation: list[str] = field(default_factory=list)


def _normalise(probabilities: dict[DecisionOutcome, float]) -> dict[DecisionOutcome, float]:
    """Ensure every outcome is present and the distribution sums to 1.

    The classifier only emits classes it saw in training; a missing class
    must read as zero probability rather than a KeyError downstream.
    """
    full = {outcome: max(0.0, probabilities.get(outcome, 0.0)) for outcome in DecisionOutcome}
    total = sum(full.values())
    if total <= 0:
        # No usable signal — spread evenly rather than inventing a winner.
        even = 1.0 / len(DecisionOutcome)
        return dict.fromkeys(DecisionOutcome, even)
    return {outcome: value / total for outcome, value in full.items()}


def recommend(
    probabilities: dict[DecisionOutcome, float], policy_effect: Effect
) -> tuple[DecisionOutcome, bool, float]:
    """Decide the recommended path.

    Policy is a hard constraint; the model is advisory. A statistical
    prediction must never unblock something the rules explicitly forbid —
    but it *may* escalate something the rules happen to permit, which is how
    the engine catches risk the policy set does not encode.

    Returns (recommendation, policy_forced, adverse_probability).
    """
    adverse = probabilities[DecisionOutcome.ESCALATED] + probabilities[DecisionOutcome.BLOCKED]

    if policy_effect in (Effect.BLOCK, Effect.REQUIRE_HUMAN_REVIEW):
        return EFFECT_TO_OUTCOME[policy_effect], True, adverse

    if adverse >= ADVERSE_ESCALATION_THRESHOLD:
        return DecisionOutcome.ESCALATED, False, adverse

    return DecisionOutcome.APPROVED, False, adverse


def simulate(
    *,
    probabilities: dict[DecisionOutcome, float],
    policy_effect: Effect,
    amount_usd: float | None,
    risk_score: int,
) -> SimulationVerdict:
    """Reduce trust, policy, and predicted probabilities to one verdict."""
    probs = _normalise(probabilities)
    recommendation, policy_forced, adverse = recommend(probs, policy_effect)

    # An action with no monetary value (a card freeze, say) still has a
    # recommendation — it simply has no exposure to weigh.
    amount = amount_usd or 0.0

    outcomes = [
        PredictedOutcome(
            outcome=outcome,
            label=OUTCOME_LABELS[outcome],
            probability=round(probs[outcome], 4),
            # Only approval moves money.
            financial_impact_usd=round(amount if outcome is DecisionOutcome.APPROVED else 0.0, 2),
            risk_score=int(round(risk_score * RESIDUAL_RISK_FACTOR[outcome])),
            # A path is compliant when the rules would permit it. With a
            # blocking rule in force, "executes as requested" is a real
            # prediction but not an allowed one — worth showing, not hiding.
            compliant=outcome is not DecisionOutcome.APPROVED or policy_effect is Effect.ALLOW,
            recommended=outcome is recommendation,
        )
        for outcome in DecisionOutcome
    ]

    approved_p = probs[DecisionOutcome.APPROVED]
    # Following the recommendation is deterministic: approve and the money
    # moves, otherwise it does not.
    exposure = amount if recommendation is DecisionOutcome.APPROVED else 0.0

    verdict = SimulationVerdict(
        recommendation=recommendation,
        outcomes=outcomes,
        confidence=round(probs[recommendation] * 100, 1),
        expected_exposure_usd=round(exposure, 2),
        withheld_usd=round(amount - exposure, 2),
        unconstrained_exposure_usd=round(approved_p * amount, 2),
        adverse_probability=round(adverse, 4),
        policy_forced=policy_forced,
        explanation=_explain(
            probs=probs,
            policy_effect=policy_effect,
            recommendation=recommendation,
            policy_forced=policy_forced,
            adverse=adverse,
            amount=amount,
            exposure=exposure,
        ),
    )
    return verdict


def _explain(
    *,
    probs: dict[DecisionOutcome, float],
    policy_effect: Effect,
    recommendation: DecisionOutcome,
    policy_forced: bool,
    adverse: float,
    amount: float,
    exposure: float,
) -> list[str]:
    lines = [
        "Predicted outcomes: "
        + ", ".join(f"{o.value} {probs[o] * 100:.0f}%" for o in DecisionOutcome),
    ]

    if policy_forced:
        lines.append(
            f"Policy returned '{policy_effect.value}', which is binding — "
            "the model's prediction cannot override an explicit rule."
        )
    elif recommendation is DecisionOutcome.ESCALATED:
        lines.append(
            f"Rules permit this action, but the model puts {adverse * 100:.0f}% on a "
            f"non-approval path (threshold {ADVERSE_ESCALATION_THRESHOLD * 100:.0f}%) — "
            "escalating on model signal the policy set does not encode."
        )
    else:
        lines.append(
            f"Rules permit this action and adverse probability is {adverse * 100:.0f}%, "
            f"below the {ADVERSE_ESCALATION_THRESHOLD * 100:.0f}% escalation threshold."
        )

    if amount:
        if exposure:
            lines.append(f"Exposure if followed: ${exposure:,.2f} of ${amount:,.2f} requested.")
        else:
            unconstrained = probs[DecisionOutcome.APPROVED] * amount
            lines.append(
                f"No money moves if this recommendation is followed. An unpoliced system "
                f"would have exposed about ${unconstrained:,.2f} of the ${amount:,.2f} "
                "requested."
            )
    else:
        lines.append("No monetary amount attached to this action.")

    lines.append(f"Recommendation: {recommendation.value}")
    return lines
