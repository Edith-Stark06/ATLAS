from datetime import date, datetime
from typing import Any, Literal

from pydantic import Field, field_validator

from app.models.enums import ActivityTone, DecisionOutcome, LifecycleState, Severity
from app.schemas.base import ApiModel
from app.services.trust_engine import FACTOR_WEIGHTS


class TrustFactorRead(ApiModel):
    key: str
    label: str
    score: int
    weight: float


class AgentRead(ApiModel):
    id: str
    name: str
    capability: str
    owner: str
    lifecycle: LifecycleState
    trust_score: int
    trust_delta: float
    decisions_today: int
    last_active_at: datetime
    model: str
    authority_level: int
    last_audit_at: date
    last_decision: str
    factors: list[TrustFactorRead] = []


class CreateAgentRequest(ApiModel):
    #: External identifier — assigned by the registering system, not
    #: generated here, matching every seeded agent's "agt-*" convention.
    #: Primary key, so it must be unique; a collision is a 409.
    id: str = Field(min_length=1, max_length=64, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    name: str = Field(min_length=1, max_length=200)
    #: Groups this agent into a benchmark cohort — ranking only ever compares
    #: agents sharing this exact string (benchmark_engine.rank_cohort).
    capability: str = Field(min_length=1, max_length=120)
    owner: str = Field(min_length=1, max_length=120)
    #: Free-text description of what the agent runs on (e.g. a model name or
    #: version) — descriptive only, not evaluated by any governance rule.
    model: str = Field(min_length=1, max_length=80)
    authority_level: int = Field(default=1, ge=1, le=4)
    #: Starting factor scores, 0-100. A newly registered agent has no track
    #: record yet, so any factor left unset defaults to a neutral 50 —
    #: ATLAS does not assert trust it hasn't observed. Keys must be a subset
    #: of the five canonical factors (trust_engine.FACTOR_WEIGHTS); an
    #: unknown key is rejected rather than silently ignored.
    factors: dict[str, int] | None = None

    @field_validator("factors")
    @classmethod
    def _validate_factors(cls, value: dict[str, int] | None) -> dict[str, int] | None:
        if value is None:
            return value
        unknown = set(value) - set(FACTOR_WEIGHTS)
        if unknown:
            raise ValueError(
                f"unknown factor(s): {sorted(unknown)} — expected one of {sorted(FACTOR_WEIGHTS)}"
            )
        out_of_range = {k: v for k, v in value.items() if not (0 <= v <= 100)}
        if out_of_range:
            raise ValueError(f"factor scores must be 0-100: {out_of_range}")
        return value


class PolicyCheckRead(ApiModel):
    policy_id: str
    policy_name: str
    passed: bool
    detail: str | None = None


class DecisionRead(ApiModel):
    id: str
    agent_id: str
    action: str
    # Declared float (not Decimal) so JSON carries a number, matching the
    # TypeScript `number | null`. Storage stays Numeric for exactness.
    amount_usd: float | None = None
    outcome: DecisionOutcome
    trust_score: int
    risk_score: int
    decided_at: datetime
    latency_ms: int
    rationale: str
    investigation: dict[str, Any] | None = None
    policy_checks: list[PolicyCheckRead] = []
    agent_name: str = ""


class PolicyRead(ApiModel):
    id: str
    name: str
    version: str
    scope: str
    enabled: bool
    severity: Severity
    evaluations_24h: int
    violations_24h: int
    updated_at: datetime


class SimulationOutcomeRead(ApiModel):
    label: str
    probability: float
    financial_impact_usd: float
    risk_score: int
    compliant: bool
    customer_experience: str | None = None
    compliance_risk: str | None = None
    recommended: bool = False


class SimulationRunRead(ApiModel):
    id: str
    decision_id: str
    scenario: str
    agent_name: str
    amount_usd: float | None = None
    trust_score: int
    confidence: float
    recommendation: DecisionOutcome
    ran_at: datetime
    duration_ms: int
    request: list[dict[str, Any]] = []
    outcomes: list[SimulationOutcomeRead] = []


class ActivityItemRead(ApiModel):
    id: str
    message: str
    at: datetime
    tone: ActivityTone


class DashboardMetric(ApiModel):
    key: str
    label: str
    value: str
    tone: Literal["primary", "secondary", "tertiary", "error"]
    icon: str


class PipelineStage(ApiModel):
    key: str
    label: str
    status: Literal["done", "active", "pending", "failed"]
    detail: str | None = None


class CompositeTrust(ApiModel):
    score: int
    # None until the Trust Engine (Phase 3) produces real forecasts. Extrapolating
    # the trend below would be misleading — it samples across different agents,
    # so it is not a time series of any single thing.
    predicted: int | None = None
    factors: list[TrustFactorRead]
    trend: list[int]


class LivePipeline(ApiModel):
    transaction_id: str
    stages: list[PipelineStage]


class DashboardRead(ApiModel):
    metrics: list[DashboardMetric]
    composite_trust: CompositeTrust
    live_pipeline: LivePipeline
    activity: list[ActivityItemRead]
