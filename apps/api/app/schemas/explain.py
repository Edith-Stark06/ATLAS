from app.models.enums import DecisionOutcome
from app.schemas.base import ApiModel
from app.services.policy_engine import Effect


class CounterfactualRead(ApiModel):
    field: str
    label: str
    current: float | None
    threshold: float
    #: "at most" or "at least" — how `threshold` should be read.
    direction: str
    changes_to: DecisionOutcome
    #: "policy" — arithmetic from a rule boundary, or "model" — found by
    #: searching the classifier's response. The distinction is deliberately
    #: exposed: one is a fact about the rules, the other an empirical probe.
    source: str
    #: True only for policy boundaries.
    exact: bool
    detail: str


class DriverRead(ApiModel):
    key: str
    label: str
    #: Signed SHAP contribution. Positive raises trust, negative lowers it.
    contribution: float
    value: float | None


class RuleEvidenceRead(ApiModel):
    policy_id: str
    policy_name: str
    version: str
    matched: bool
    in_scope: bool
    effect: Effect | None


class ExplanationRead(ApiModel):
    decision_id: str
    agent_id: str
    agent_name: str
    action: str

    outcome: DecisionOutcome
    headline: str
    #: "policy" when a rule was binding, "model" otherwise.
    decided_by: str
    narrative: list[str]

    drivers: list[DriverRead]
    #: True when `drivers` describe the agent's trust *today* rather than at
    #: decision time. Per-factor attribution is not snapshotted, so this is
    #: flagged rather than presented as historical.
    drivers_are_current: bool

    rules: list[RuleEvidenceRead]
    counterfactuals: list[CounterfactualRead]

    #: Ledger position this was reconstructed from, if any.
    ledger_seq: int | None
    #: False when no audit record backs this explanation — a weaker claim,
    #: and the reader should be able to see that.
    from_pinned_evidence: bool
