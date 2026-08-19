from datetime import date, datetime
from typing import Any, Literal

from app.models.enums import ActivityTone, DecisionOutcome, LifecycleState, Severity
from app.schemas.base import ApiModel


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
