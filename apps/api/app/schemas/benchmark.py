from app.schemas.base import ApiModel


class CohortRead(ApiModel):
    capability: str
    agents: int


class CriterionRead(ApiModel):
    key: str
    label: str
    #: 0–100, on a fixed scale. Deliberately not normalised within the cohort:
    #: that would make the best member 100 by construction.
    score: float
    weight: float
    #: What the score was computed from, in a unit an operator recognises.
    basis: str
    #: score × weight — the criterion's share of the composite.
    contribution: float


class AgentScoreRead(ApiModel):
    agent_id: str
    agent_name: str
    capability: str
    composite: float
    criteria: list[CriterionRead]
    decisions: int
    #: Too little activity for the rates to be a track record.
    thin_evidence: bool


class GapRead(ApiModel):
    key: str
    label: str
    agent_score: float
    leader_score: float
    points: float
    #: How much of the composite gap this criterion accounts for. Ranked on
    #: this rather than on raw points, so the list reflects what would
    #: actually move the score.
    composite_cost: float


class BenchmarkRead(ApiModel):
    capability: str
    window_days: int
    #: Published with the ranking: a weighting that cannot be inspected turns
    #: an opinion into an apparent measurement.
    weights: dict[str, float]
    scored: list[AgentScoreRead]
    leader_id: str | None
    #: False for a cohort of one — a "ranking" of a single agent is not one.
    comparable: bool
    gaps: dict[str, list[GapRead]]


class ContributionRead(ApiModel):
    key: str
    label: str
    before: float
    after: float
    #: Signed points of the total change attributable to this factor.
    contribution: float
    #: The factor's own movement.
    from_value: float
    #: The factor's weight being re-tuned. A different event from the above,
    #: and a reader needs to know which one happened.
    from_weight: float


class ChangeAttributionRead(ApiModel):
    agent_id: str
    window_days: int
    before_score: float
    after_score: float
    delta: float
    contributions: list[ContributionRead]
    #: Subtracted from the base score, so attributable to no single factor.
    penalty_delta: float
    #: What the decomposition cannot account for, stated rather than spread
    #: across the factors.
    residual: float
    #: The residual as a share of the whole change, 0-1. A large value is a
    #: real finding rather than a defect: the score comes from a trained
    #: model, not the weighted sum this decomposition assumes, so the model
    #: moved the score for reasons the factors do not capture.
    residual_share: float
    #: True when the parts sum exactly to the whole. False means the breakdown
    #: should not be trusted, and the client should say so.
    reconciles: bool
