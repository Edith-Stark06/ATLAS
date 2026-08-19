from datetime import datetime

from app.models.enums import LifecycleState
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
