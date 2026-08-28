"""The Policy Brain.

Evaluates structured, versioned governance rules against a decision context.

A rule is data, not code: a list of conditions over a fixed set of evaluable
fields, combined with all/any, producing an effect. That makes rules
storable, versionable, diffable, and — critically — simulatable against
historical decisions before they are deployed, none of which is possible if
policies are hand-written Python branches.

Pure functions over plain values: no database, no ORM, no I/O. The service
layer (app/services/policy_service.py) is what talks to Postgres.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

# --- Rule vocabulary --------------------------------------------------------


class Operator(StrEnum):
    LT = "lt"
    LTE = "lte"
    GT = "gt"
    GTE = "gte"
    EQ = "eq"
    NEQ = "neq"
    IN = "in"
    NOT_IN = "not_in"


class Combinator(StrEnum):
    ALL = "all"
    ANY = "any"


class Effect(StrEnum):
    """What happens when a rule matches.

    ALLOW is deliberately available: an explicit allow-rule can carve an
    exception out of a broader restriction, and is more auditable than
    encoding the exception as a negation inside the restrictive rule.
    """

    ALLOW = "allow"
    REQUIRE_HUMAN_REVIEW = "require_human_review"
    BLOCK = "block"


#: Effects ordered by how restrictive they are. When several rules match one
#: decision, the most restrictive wins — a policy engine must never let an
#: permissive rule silently override a block.
EFFECT_PRECEDENCE = {Effect.ALLOW: 0, Effect.REQUIRE_HUMAN_REVIEW: 1, Effect.BLOCK: 2}


@dataclass(frozen=True)
class FieldSpec:
    label: str
    kind: type
    description: str


#: Fields every domain shares. Trust, risk, amount and lifecycle mean the
#: same thing whatever the agent does.
#:
#: The vocabulary stays closed — a rule may only reference known fields, so
#: evaluation never reaches for an arbitrary attribute and the authoring UI can
#: offer a real picker. It is simply core *plus* whatever vertical packs
#: declare; see `evaluable_fields()`.
CORE_FIELDS: dict[str, FieldSpec] = {
    "trust_score": FieldSpec("Trust Score", int, "Agent trust at decision time, 0–100"),
    "risk_score": FieldSpec("Risk Score", int, "Assessed risk of the action, 0–100"),
    "amount_usd": FieldSpec(
        "Amount (USD)", float, "Transaction value; absent for non-financial actions"
    ),
    "authority_level": FieldSpec("Authority Level", int, "Agent autonomy tier, 1–4"),
    "agent_lifecycle": FieldSpec(
        "Lifecycle State", str, "onboarding, healthy, trusted, anomaly, review, recovery"
    ),
    "capability": FieldSpec("Capability", str, "Business domain, e.g. 'Payments'"),
    "hour_utc": FieldSpec("Hour (UTC)", int, "Hour of day the action was requested, 0–23"),
}


def evaluable_fields() -> dict[str, FieldSpec]:
    """Every field a rule may reference: core plus registered vertical packs.

    Resolved on call rather than at import: the packs import `FieldSpec` from
    this module, so computing it eagerly would be a circular import. The
    result is small and the call is cheap.
    """
    from app.domains import domain_fields

    return {**CORE_FIELDS, **domain_fields()}


#: Operators that need an ordered comparison, so they cannot be applied to
#: strings or to a missing value.
NUMERIC_OPERATORS = {Operator.LT, Operator.LTE, Operator.GT, Operator.GTE}

#: Operators whose operand is a collection rather than a scalar.
MEMBERSHIP_OPERATORS = {Operator.IN, Operator.NOT_IN}


# --- Rule structures --------------------------------------------------------


@dataclass(frozen=True)
class Condition:
    field: str
    operator: Operator
    value: Any

    def describe(self) -> str:
        spec = evaluable_fields().get(self.field)
        label = spec.label if spec else self.field
        symbol = {
            Operator.LT: "<",
            Operator.LTE: "≤",
            Operator.GT: ">",
            Operator.GTE: "≥",
            Operator.EQ: "is",
            Operator.NEQ: "is not",
            Operator.IN: "in",
            Operator.NOT_IN: "not in",
        }[self.operator]
        return f"{label} {symbol} {self.value}"


@dataclass(frozen=True)
class Rule:
    conditions: list[Condition]
    combinator: Combinator
    effect: Effect
    #: Capabilities this rule governs. Empty means every agent.
    applies_to: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class PolicyContext:
    """Everything a rule is allowed to see about one decision."""

    trust_score: int
    risk_score: int
    amount_usd: float | None
    authority_level: int
    agent_lifecycle: str
    capability: str
    hour_utc: int

    #: Domain values contributed by a vertical pack — portfolio concentration,
    #: destination risk tier, inventory remaining. Absent keys stay absent
    #: rather than defaulting: a funds rule evaluated against a travel decision
    #: must decline to fire, not read a missing concentration as 0% and block
    #: something it knows nothing about.
    attributes: dict[str, Any] = field(default_factory=dict)

    def get(self, field_name: str) -> Any:
        """Core fields first, then domain attributes.

        Core wins a name clash so a pack cannot shadow `risk_score` and
        quietly change what every existing rule means.
        """
        if field_name in CORE_FIELDS:
            return getattr(self, field_name, None)
        return self.attributes.get(field_name)


@dataclass(frozen=True)
class ConditionResult:
    condition: Condition
    matched: bool
    actual: Any
    #: Set when the condition could not be evaluated at all (missing value,
    #: type mismatch) as opposed to evaluating cleanly to False.
    skipped_reason: str | None = None

    def describe(self) -> str:
        if self.skipped_reason:
            return f"{self.condition.describe()} — not evaluated ({self.skipped_reason})"
        verdict = "met" if self.matched else "not met"
        return f"{self.condition.describe()} — {verdict} (actual: {self.actual})"


@dataclass(frozen=True)
class RuleEvaluation:
    matched: bool
    effect: Effect | None
    results: list[ConditionResult]
    #: False when the rule's applies_to excluded this agent entirely, in
    #: which case no conditions were evaluated.
    in_scope: bool = True
    explanation: list[str] = field(default_factory=list)


# --- Parsing ----------------------------------------------------------------


class RuleValidationError(ValueError):
    """A stored or submitted rule is not evaluable."""


def parse_condition(raw: dict) -> Condition:
    try:
        field_name = raw["field"]
        operator = Operator(raw["operator"])
        value = raw["value"]
    except (KeyError, ValueError) as exc:
        raise RuleValidationError(f"Malformed condition {raw!r}: {exc}") from exc

    fields = evaluable_fields()
    spec = fields.get(field_name)
    if spec is None:
        allowed = ", ".join(sorted(fields))
        raise RuleValidationError(f"Unknown field '{field_name}'. Allowed: {allowed}")

    if operator in MEMBERSHIP_OPERATORS:
        if not isinstance(value, (list, tuple)):
            raise RuleValidationError(f"Operator '{operator}' needs a list value, got {value!r}")
    elif operator in NUMERIC_OPERATORS and spec.kind is str:
        raise RuleValidationError(
            f"Operator '{operator}' cannot order a text field ('{field_name}')"
        )
    elif operator in NUMERIC_OPERATORS and not isinstance(value, (int, float)):
        raise RuleValidationError(f"Operator '{operator}' needs a number, got {value!r}")

    return Condition(field=field_name, operator=operator, value=value)


def parse_rule(raw: dict) -> Rule:
    """Build a Rule from stored JSONB, rejecting anything not evaluable.

    Validation happens on the way in (authoring) and on the way out
    (evaluation) — a rule that was valid when written could reference a
    field later removed from EVALUABLE_FIELDS, and failing loudly beats
    silently never matching.
    """
    conditions = [parse_condition(c) for c in raw.get("conditions", [])]
    if not conditions:
        raise RuleValidationError("A rule needs at least one condition")

    try:
        combinator = Combinator(raw.get("combinator", "all"))
        effect = Effect(raw["effect"])
    except (KeyError, ValueError) as exc:
        raise RuleValidationError(f"Malformed rule: {exc}") from exc

    applies_to = raw.get("applies_to") or []
    if not isinstance(applies_to, list):
        raise RuleValidationError(f"applies_to must be a list, got {applies_to!r}")

    return Rule(
        conditions=conditions, combinator=combinator, effect=effect, applies_to=list(applies_to)
    )


def rule_to_dict(rule: Rule) -> dict:
    return {
        "conditions": [
            {"field": c.field, "operator": c.operator.value, "value": c.value}
            for c in rule.conditions
        ],
        "combinator": rule.combinator.value,
        "effect": rule.effect.value,
        "applies_to": list(rule.applies_to),
    }


# --- Evaluation -------------------------------------------------------------


def evaluate_condition(condition: Condition, context: PolicyContext) -> ConditionResult:
    """Evaluate one condition, never raising.

    A missing value (e.g. amount_usd on a card-freeze action, which has no
    amount) does not match an ordered comparison and is reported as skipped
    rather than as a clean False — "we could not tell" and "we checked and
    it was under the limit" are different facts, and an audit trail that
    conflates them is misleading.
    """
    actual = context.get(condition.field)

    if actual is None:
        return ConditionResult(
            condition=condition,
            matched=False,
            actual=None,
            skipped_reason=f"{condition.field} is not set for this action",
        )

    try:
        match condition.operator:
            case Operator.LT:
                matched = actual < condition.value
            case Operator.LTE:
                matched = actual <= condition.value
            case Operator.GT:
                matched = actual > condition.value
            case Operator.GTE:
                matched = actual >= condition.value
            case Operator.EQ:
                matched = actual == condition.value
            case Operator.NEQ:
                matched = actual != condition.value
            case Operator.IN:
                matched = actual in condition.value
            case Operator.NOT_IN:
                matched = actual not in condition.value
            case _:  # pragma: no cover - Operator is exhaustive
                raise RuleValidationError(f"Unhandled operator {condition.operator}")
    except TypeError as exc:
        return ConditionResult(
            condition=condition,
            matched=False,
            actual=actual,
            skipped_reason=f"type mismatch ({exc})",
        )

    return ConditionResult(condition=condition, matched=bool(matched), actual=actual)


def evaluate_rule(rule: Rule, context: PolicyContext) -> RuleEvaluation:
    """Evaluate a rule against one decision context."""
    if rule.applies_to and context.capability not in rule.applies_to:
        return RuleEvaluation(
            matched=False,
            effect=None,
            results=[],
            in_scope=False,
            explanation=[
                f"Out of scope: rule governs {', '.join(rule.applies_to)}; "
                f"this agent is {context.capability}"
            ],
        )

    results = [evaluate_condition(c, context) for c in rule.conditions]

    if rule.combinator is Combinator.ALL:
        matched = all(r.matched for r in results)
    else:
        matched = any(r.matched for r in results)

    explanation = [r.describe() for r in results]
    joiner = "all conditions" if rule.combinator is Combinator.ALL else "any condition"
    explanation.append(
        f"Rule {'matched' if matched else 'did not match'} ({joiner} required) → "
        f"{rule.effect.value if matched else 'no effect'}"
    )

    return RuleEvaluation(
        matched=matched,
        effect=rule.effect if matched else None,
        results=results,
        explanation=explanation,
    )


@dataclass(frozen=True)
class PolicyDecision:
    """The Policy Brain's combined verdict over every applicable policy."""

    effect: Effect
    #: Policies whose rule matched, most restrictive first.
    triggered: list[tuple[str, str, Effect]]
    #: (policy_id, policy_name) pairs that were evaluated but did not match.
    passed: list[tuple[str, str]]
    #: Policies skipped because their scope excluded this agent.
    out_of_scope: list[tuple[str, str]]
    explanation: list[str]


def combine(evaluations: list[tuple[str, str, Rule, RuleEvaluation]]) -> PolicyDecision:
    """Reduce per-policy evaluations to one governance effect.

    Most restrictive wins (EFFECT_PRECEDENCE). With no matching rule the
    default is ALLOW — policies are restrictions on an otherwise permitted
    action, not an allowlist. Making the default BLOCK would mean an empty
    policy set halts the whole estate, which is not a safe failure mode for
    a system whose policies are edited live.
    """
    triggered: list[tuple[str, str, Effect]] = []
    passed: list[tuple[str, str]] = []
    out_of_scope: list[tuple[str, str]] = []

    for policy_id, policy_name, _rule, evaluation in evaluations:
        if not evaluation.in_scope:
            out_of_scope.append((policy_id, policy_name))
        elif evaluation.matched and evaluation.effect is not None:
            triggered.append((policy_id, policy_name, evaluation.effect))
        else:
            passed.append((policy_id, policy_name))

    triggered.sort(key=lambda t: EFFECT_PRECEDENCE[t[2]], reverse=True)
    effect = triggered[0][2] if triggered else Effect.ALLOW

    explanation = []
    if triggered:
        for policy_id, policy_name, policy_effect in triggered:
            explanation.append(f"{policy_name} ({policy_id}) → {policy_effect.value}")
        explanation.append(
            f"Most restrictive effect applied: {effect.value}"
            if len(triggered) > 1
            else f"Effect applied: {effect.value}"
        )
    else:
        explanation.append(
            f"No policy matched ({len(passed)} evaluated, {len(out_of_scope)} out of scope) → allow"
        )

    return PolicyDecision(
        effect=effect,
        triggered=triggered,
        passed=passed,
        out_of_scope=out_of_scope,
        explanation=explanation,
    )


def context_from_decision(
    *,
    trust_score: int,
    risk_score: int,
    amount_usd: float | None,
    authority_level: int,
    agent_lifecycle: str,
    capability: str,
    decided_at: datetime,
) -> PolicyContext:
    return PolicyContext(
        trust_score=trust_score,
        risk_score=risk_score,
        amount_usd=amount_usd,
        authority_level=authority_level,
        agent_lifecycle=agent_lifecycle,
        capability=capability,
        hour_utc=decided_at.hour,
    )
