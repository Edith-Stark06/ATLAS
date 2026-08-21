from pydantic import Field

from app.models.enums import DecisionOutcome
from app.schemas.base import ApiModel
from app.services.policy_engine import Effect


class SimulateActionRequest(ApiModel):
    """A proposed action to evaluate before it runs."""

    action: str = Field(default="Proposed action", max_length=300)
    #: When set, the agent's stored trust, capability and lifecycle are used.
    agent_id: str | None = None
    amount_usd: float | None = None
    risk_score: int = Field(default=20, ge=0, le=100)
    #: Overrides the agent's stored score — this is what makes
    #: "what if trust dropped to 40?" answerable.
    trust_score: int | None = Field(default=None, ge=0, le=100)
    hour_utc: int | None = Field(default=None, ge=0, le=23)
    policy_pass_rate: float = Field(default=1.0, ge=0.0, le=1.0)


class PredictedOutcomeRead(ApiModel):
    outcome: DecisionOutcome
    label: str
    probability: float
    financial_impact_usd: float
    #: Residual risk if this path is taken, 0–100.
    risk_score: int
    #: Whether the active rules would permit this path.
    compliant: bool
    recommended: bool


class PolicyTraceRead(ApiModel):
    policy_id: str
    policy_name: str
    version: str
    matched: bool
    in_scope: bool
    effect: Effect | None = None


class SimulateActionResponse(ApiModel):
    recommendation: DecisionOutcome
    #: Confidence in the recommended path, 0–100.
    confidence: float
    outcomes: list[PredictedOutcomeRead]

    #: Money that moves if the recommendation is followed. Deterministic —
    #: nothing moves once the recommendation is to block or escalate.
    expected_exposure_usd: float
    withheld_usd: float
    #: What an unpoliced system would expose on average. The gap against
    #: expected_exposure_usd is what the governance layer is buying.
    unconstrained_exposure_usd: float
    adverse_probability: float

    #: True when the rules, not the model, determined the recommendation.
    policy_forced: bool
    policy_effect: Effect
    policy_trace: list[PolicyTraceRead]

    agent_name: str
    trust_score: int
    #: False when no trained classifier is loaded — probabilities are then an
    #: even split, which reads as "no signal" rather than a confident guess.
    model_backed: bool
    duration_ms: int
    explanation: list[str]


class RebuildResponse(ApiModel):
    rebuilt: int
