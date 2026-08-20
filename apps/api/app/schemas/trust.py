from datetime import datetime

from app.models.enums import DecisionOutcome, LifecycleState
from app.schemas.base import ApiModel
from app.schemas.governance import TrustFactorRead


class DriftRead(ApiModel):
    detected: bool
    #: Current score minus the agent's own historical baseline, in points.
    delta: float
    baseline: float | None = None
    samples: int


class TrustSnapshotRead(ApiModel):
    score: int
    base_score: float
    anomaly_penalty: float
    reason: str
    captured_at: datetime


class MLAnomalyRead(ApiModel):
    detected: bool
    #: Isolation Forest decision_function output — more negative is more
    #: anomalous. Not a fixed 0-100 scale like the heuristic drift delta.
    score: float


class TrustEvaluationRead(ApiModel):
    agent_id: str
    agent_name: str
    score: int
    base_score: float
    anomaly_penalty: float
    lifecycle: LifecycleState
    factors: list[TrustFactorRead]
    drift: DriftRead
    #: None when there is too little history to project honestly.
    forecast: int | None = None
    #: Step-by-step account of how the score was reached.
    explanation: list[str]
    history: list[TrustSnapshotRead]
    #: "ml" when a trained model produced `score`, "heuristic" otherwise.
    score_source: str = "heuristic"
    #: Per-factor SHAP contribution to `score`, in score units. None when
    #: score_source is "heuristic".
    ml_attribution: dict[str, float] | None = None
    #: Per-agent Isolation Forest result. None when no trained model is
    #: loaded, or the agent has too little history to fit one meaningfully.
    ml_anomaly: MLAnomalyRead | None = None


class TrustBandCount(ApiModel):
    band: str
    label: str
    count: int


class TrustOverviewRead(ApiModel):
    #: Mean score across the estate.
    average_score: int
    agents_evaluated: int
    drifting: int
    bands: list[TrustBandCount]
    #: Agents ordered by how badly they are drifting, worst first.
    watchlist: list[TrustEvaluationRead]


class RecomputeResult(ApiModel):
    agent_id: str
    agent_name: str
    previous_score: int
    score: int
    lifecycle: LifecycleState
    drift_detected: bool


class RecomputeResponse(ApiModel):
    evaluated: int
    results: list[RecomputeResult]


class SimulationPredictRequest(ApiModel):
    """A hypothetical decision to score — no persistence, no agent lookup.
    This is what powers "try a scenario" in the console, separate from the
    historical simulation runs already stored against real decisions."""

    trust_score: int
    risk_score: int
    amount_usd: float
    policy_pass_rate: float
    authority_level: int
    hour: int = 12


class PredictedOutcome(ApiModel):
    outcome: DecisionOutcome
    probability: float


class SimulationPredictResponse(ApiModel):
    outcomes: list[PredictedOutcome]
    #: The outcome with the highest predicted probability.
    recommendation: DecisionOutcome


class ModelInfoRead(ApiModel):
    #: False when no trained artifacts exist yet (fresh clone before
    #: `python -m app.ml.train` has run) — everything else is None in that case.
    available: bool
    trained_at: str | None = None
    #: Full baseline-vs-learned comparison report from training, unmodified —
    #: the quantitative evidence backing the trained-vs-heuristic claims made
    #: elsewhere in the API and console.
    metrics: dict | None = None
