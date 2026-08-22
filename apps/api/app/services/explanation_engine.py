"""Why a decision came out the way it did — and what would change it.

Three of the four things an explanation needs already exist elsewhere: the
trust model's SHAP attribution, the policy engine's per-condition results, and
the simulation engine's prose. This module adds the fourth, which is the one
that makes an explanation actionable rather than merely descriptive:

    "Blocked. It would have been approved at a risk score of 89 or below."

Pure functions over plain values — no database, no model loading — so the
counterfactual logic can be tested exhaustively.

Two sources of counterfactual, with very different epistemic status, and the
distinction is preserved in the output rather than blurred:

- **Policy** boundaries are *exact*. A rule is `risk_score > 90`; the value
  that stops it matching is arithmetic, not estimation.
- **Model** boundaries are *found by search*. A gradient-boosted classifier
  is not monotonic, so this scans the feature's real range instead of
  bisecting it — a binary search would silently return a wrong boundary
  wherever the response is non-monotone.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.models.enums import DecisionOutcome
from app.services.policy_engine import (
    EVALUABLE_FIELDS,
    Condition,
    ConditionResult,
    Effect,
    Operator,
)

#: Fields a counterfactual may suggest changing, with their valid range and
#: step. Deliberately a closed list: suggesting "change the capability to
#: Payments" is not advice anyone can act on, and suggesting a change to
#: `agent_lifecycle` would be telling an operator to fake a governance state.
SEARCHABLE_FIELDS: dict[str, tuple[float, float, float]] = {
    # field: (minimum, maximum, step)
    "risk_score": (0, 100, 1),
    "trust_score": (0, 100, 1),
    "amount_usd": (0, 1_000_000, 50),
}

#: How far the model search will look before giving up. A scan over the whole
#: amount range at a 50-dollar step is 20k predictions, which is too slow for
#: a request; the search stops once it has looked this many steps either side.
MAX_SEARCH_STEPS = 400


@dataclass(frozen=True)
class Counterfactual:
    """A single change that would have produced a different verdict."""

    field: str
    label: str
    current: float | None
    #: The value at which the outcome changes.
    threshold: float
    #: "at most" or "at least" — how `threshold` should be read.
    direction: str
    changes_to: DecisionOutcome
    #: "policy" (exact, from a rule boundary) or "model" (found by search).
    source: str
    detail: str

    @property
    def exact(self) -> bool:
        return self.source == "policy"


@dataclass(frozen=True)
class Driver:
    """One factor that pushed the verdict, with its contribution."""

    key: str
    label: str
    #: Signed. Positive raises trust, negative lowers it.
    contribution: float
    value: float | None = None


@dataclass(frozen=True)
class RuleEvidence:
    policy_id: str
    policy_name: str
    version: str
    matched: bool
    in_scope: bool
    effect: Effect | None
    #: One line per condition, with the actual value it was tested against.
    conditions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class Explanation:
    outcome: DecisionOutcome
    #: The single sentence a reviewer reads first.
    headline: str
    #: What decided it: "policy" when a rule was binding, "model" otherwise.
    decided_by: str
    narrative: list[str] = field(default_factory=list)
    drivers: list[Driver] = field(default_factory=list)
    rules: list[RuleEvidence] = field(default_factory=list)
    counterfactuals: list[Counterfactual] = field(default_factory=list)


# --- policy counterfactuals (exact) ------------------------------------------

#: For a matched condition, the value just outside the range that matched.
#: Integer fields step by 1; a float field cannot have a "next" value, so the
#: boundary itself is reported and the wording carries the strictness.
_BOUNDARY = {
    Operator.GT: lambda v, step: v,  # matched x > v; x = v no longer matches
    Operator.GTE: lambda v, step: v - step,
    Operator.LT: lambda v, step: v,
    Operator.LTE: lambda v, step: v + step,
}

_DIRECTION = {
    Operator.GT: "at most",
    Operator.GTE: "at most",
    Operator.LT: "at least",
    Operator.LTE: "at least",
}


def _step_for(field_name: str) -> float:
    spec = EVALUABLE_FIELDS.get(field_name)
    if spec is None:
        return 1
    return 1 if spec.kind is int else 0.01


def condition_boundary(condition: Condition, actual: float | None) -> Counterfactual | None:
    """The exact value at which a matched numeric condition stops matching.

    Returns None for conditions no operator arithmetic applies to — set
    membership and equality on strings have no "just outside" value, and
    inventing one would be worse than saying nothing.
    """
    if condition.operator not in _BOUNDARY:
        return None
    if not isinstance(condition.value, int | float) or isinstance(condition.value, bool):
        return None

    spec = EVALUABLE_FIELDS.get(condition.field)
    label = spec.label if spec else condition.field
    step = _step_for(condition.field)
    threshold = _BOUNDARY[condition.operator](float(condition.value), step)
    direction = _DIRECTION[condition.operator]

    return Counterfactual(
        field=condition.field,
        label=label,
        current=actual,
        threshold=threshold,
        direction=direction,
        # The rule stops matching, so its restrictive effect stops applying.
        # What the verdict becomes then depends on the remaining rules and the
        # model, so this is stated as approval only by the caller, which knows.
        changes_to=DecisionOutcome.APPROVED,
        source="policy",
        detail=f"{label} would need to be {direction} {_fmt(threshold)} for this rule not to fire",
    )


def _fmt(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else f"{value:,.2f}"


def policy_counterfactuals(
    binding: list[tuple[Condition, ConditionResult]],
) -> list[Counterfactual]:
    """Exact boundaries for every matched numeric condition of a binding rule.

    All of them, not just one: a rule combined with `all` needs only a single
    condition to stop matching, so each is independently sufficient — and an
    operator should see the full set of options rather than an arbitrary pick.
    """
    out = []
    for condition, result in binding:
        if not result.matched:
            continue
        actual = result.actual if isinstance(result.actual, int | float) else None
        counterfactual = condition_boundary(condition, actual)
        if counterfactual is not None:
            out.append(counterfactual)
    return out


# --- model counterfactuals (searched) ----------------------------------------


def model_counterfactual(
    *,
    field_name: str,
    features: dict[str, float],
    predict: Callable[[dict[str, float]], DecisionOutcome],
    current_outcome: DecisionOutcome,
    target: DecisionOutcome = DecisionOutcome.APPROVED,
) -> Counterfactual | None:
    """The nearest value of one feature that flips the model's verdict.

    Scans outward from the current value rather than bisecting. Gradient
    boosting produces a step function that is not guaranteed monotonic in any
    feature, and a binary search over a non-monotone response returns a
    boundary that is simply wrong — plausible-looking and unverifiable, which
    is the worst kind of answer for an audit surface.

    Returns None when no value in range flips it. That is a real and useful
    result: it means the verdict does not hinge on this input at all.
    """
    bounds = SEARCHABLE_FIELDS.get(field_name)
    if bounds is None:
        return None

    low, high, step = bounds
    current = features.get(field_name)
    if current is None:
        return None

    spec = EVALUABLE_FIELDS.get(field_name)
    label = spec.label if spec else field_name

    # Walk outward in both directions so the *nearest* flip is found, not
    # merely the first one in scan order.
    for distance in range(1, MAX_SEARCH_STEPS + 1):
        for candidate in (current - distance * step, current + distance * step):
            if candidate < low or candidate > high:
                continue
            probe = {**features, field_name: candidate}
            if predict(probe) is not target:
                continue

            direction = "at most" if candidate < current else "at least"
            return Counterfactual(
                field=field_name,
                label=label,
                current=current,
                threshold=candidate,
                direction=direction,
                changes_to=target,
                source="model",
                detail=(
                    f"the model predicts {target.value} once {label.lower()} is "
                    f"{direction} {_fmt(candidate)}"
                ),
            )

    return None


def model_counterfactuals(
    *,
    features: dict[str, float],
    predict: Callable[[dict[str, float]], DecisionOutcome],
    current_outcome: DecisionOutcome,
    target: DecisionOutcome = DecisionOutcome.APPROVED,
) -> list[Counterfactual]:
    """Nearest flip for each searchable feature, closest change first."""
    found = []
    for field_name in SEARCHABLE_FIELDS:
        counterfactual = model_counterfactual(
            field_name=field_name,
            features=features,
            predict=predict,
            current_outcome=current_outcome,
            target=target,
        )
        if counterfactual is not None:
            found.append(counterfactual)

    # Rank by how big a change is being asked for, relative to the feature's
    # own range — otherwise a $500 move always looks larger than a 5-point one.
    def relative_distance(c: Counterfactual) -> float:
        low, high, _ = SEARCHABLE_FIELDS[c.field]
        span = high - low or 1
        return abs(c.threshold - (c.current or 0)) / span

    return sorted(found, key=relative_distance)


# --- assembly ----------------------------------------------------------------


def headline(outcome: DecisionOutcome, decided_by: str, agent_name: str) -> str:
    verb = {
        DecisionOutcome.APPROVED: "was approved",
        DecisionOutcome.ESCALATED: "was held for human review",
        DecisionOutcome.BLOCKED: "was blocked",
    }[outcome]
    by = "by an explicit policy rule" if decided_by == "policy" else "by the trained model"
    return f"{agent_name}'s action {verb} {by}."


def drivers_from_attribution(
    attribution: dict[str, float] | None,
    factors: dict[str, float] | None = None,
    labels: dict[str, str] | None = None,
) -> list[Driver]:
    """Turn SHAP output into ranked drivers.

    Sorted by absolute contribution: the largest negative influence matters as
    much as the largest positive one when explaining a refusal.
    """
    if not attribution:
        return []

    labels = labels or {}
    factors = factors or {}
    ranked = sorted(attribution.items(), key=lambda kv: abs(kv[1]), reverse=True)

    return [
        Driver(
            key=key,
            label=labels.get(key, key.replace("_", " ").title()),
            contribution=round(value, 4),
            value=factors.get(key),
        )
        for key, value in ranked
    ]
