from datetime import datetime
from typing import Any

from pydantic import Field

from app.models.enums import DecisionOutcome, Severity
from app.schemas.base import ApiModel
from app.services.policy_engine import Combinator, Effect, Operator


class FieldSpecRead(ApiModel):
    """One evaluable field, so the authoring UI can build a real field
    picker rather than a free-text box."""

    key: str
    label: str
    kind: str
    description: str
    #: The vertical pack that contributes this field, or None for a core field
    #: every domain shares. The authoring UI uses this to avoid offering a
    #: travel author a mutual-funds field, which would produce a rule that can
    #: never fire.
    domain: str | None = None
    #: Capabilities this field is meaningful for. Empty means every capability.
    applies_to: list[str] = []


class RuleVocabularyRead(ApiModel):
    """Everything a client needs to compose a valid rule."""

    fields: list[FieldSpecRead]
    operators: list[str]
    combinators: list[str]
    effects: list[str]
    #: Distinct agent capabilities, for the applies_to picker.
    capabilities: list[str]
    #: Registered vertical packs, so a client can group the field picker by
    #: domain and show what each one governs.
    domains: list["DomainRead"] = []


class DomainRead(ApiModel):
    key: str
    label: str
    description: str
    capabilities: list[str]
    #: Field names this pack contributes.
    fields: list[str]


class ConditionRead(ApiModel):
    field: str
    operator: Operator
    value: Any


class RuleRead(ApiModel):
    conditions: list[ConditionRead]
    combinator: Combinator
    effect: Effect
    applies_to: list[str] = Field(default_factory=list)


class PolicyVersionRead(ApiModel):
    id: int
    policy_id: str
    version: str
    rule: dict
    note: str
    created_by: str
    created_at: datetime


class PolicyDetailRead(ApiModel):
    id: str
    name: str
    version: str
    scope: str
    enabled: bool
    severity: Severity
    updated_at: datetime
    # ApiModel's alias generator already emits evaluations24h / violations24h.
    evaluations_24h: int
    violations_24h: int
    #: None when the policy has no active version yet.
    rule: dict | None = None
    #: Human-readable rendering of the active rule.
    summary: list[str] = Field(default_factory=list)
    versions: list[PolicyVersionRead] = Field(default_factory=list)


class CreateVersionRequest(ApiModel):
    rule: dict
    version: str
    note: str = ""
    created_by: str = "console"
    activate: bool = True


class ConditionResultRead(ApiModel):
    description: str
    matched: bool
    skipped: bool


class PolicyEvaluationRead(ApiModel):
    policy_id: str
    policy_name: str
    version: str
    matched: bool
    in_scope: bool
    effect: Effect | None = None
    conditions: list[ConditionResultRead]


class EvaluateRequest(ApiModel):
    """A hypothetical decision to run the whole active policy set against."""

    trust_score: int
    risk_score: int
    amount_usd: float | None = None
    authority_level: int = 2
    agent_lifecycle: str = "healthy"
    capability: str = ""
    hour_utc: int = 12


class EvaluateResponse(ApiModel):
    effect: Effect
    outcome: DecisionOutcome
    explanation: list[str]
    evaluations: list[PolicyEvaluationRead]
    #: Policies whose stored rule could not be parsed — surfaced rather than
    #: silently skipped, since a policy that quietly stops governing is worse
    #: than one that loudly fails.
    invalid: list[str] = Field(default_factory=list)


class SimulatedDecisionRead(ApiModel):
    decision_id: str
    agent_name: str
    action: str
    recorded_outcome: DecisionOutcome
    simulated_outcome: DecisionOutcome
    matched: bool
    changed: bool


class SimulateRuleRequest(ApiModel):
    rule: dict


class SimulateRuleResponse(ApiModel):
    evaluated: int
    matched: int
    would_block: int
    would_escalate: int
    would_allow: int
    changed: list[SimulatedDecisionRead]
    sample: list[SimulatedDecisionRead]
