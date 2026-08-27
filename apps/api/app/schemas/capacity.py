from pydantic import Field

from app.schemas.base import ApiModel


class CapacityRequest(ApiModel):
    """A growth question about one job."""

    capability: str
    #: How much more volume. Clamped to 1× at the low end — this plans for
    #: growth, and silently answering "scale to 50%" would be a different
    #: question with the same shape.
    multiplier: float = Field(default=2.0, ge=1.0, le=20.0)
    #: Observation window the current rates are measured over.
    days: int = Field(default=30, ge=1, le=365)
    #: Reviewer-days available per day, today.
    reviewer_days_available: float = Field(default=1.0, ge=0)
    #: Human minutes per escalated decision. The biggest lever on the reviewer
    #: figure, so a team that has measured their own should supply it.
    review_minutes: float = Field(default=12.0, gt=0, le=480)


class ConstraintRead(ApiModel):
    key: str
    label: str
    available: float
    required: float
    unit: str
    detail: str
    #: Spare capacity as a share of what is needed, 0–1. Floors at 0 rather
    #: than going negative; `shortfall` carries the bad news in real units.
    headroom: float
    satisfied: bool
    shortfall: float


class AgentPlanRead(ApiModel):
    agent_id: str
    agent_name: str
    #: "scale" | "hold" | "fix_first" | "observe"
    action: str
    current_daily: float
    recommended_daily: float
    change_pct: float
    reason: str


class CapacityPlanRead(ApiModel):
    capability: str
    window_days: int
    multiplier: float

    current_daily: float
    target_daily: float

    constraints: list[ConstraintRead]
    #: The constraint that runs out first — the actual answer to "what do we
    #: need". Adding agents does not help when you are short of reviewers.
    binding_constraint: str | None
    feasible: bool
    #: Target volume no agent was judged safe to take. Non-zero means the plan
    #: does not reach its own target with the estate as it stands.
    unallocated_daily: float

    agents: list[AgentPlanRead]
    #: What the projection takes on faith. Stated, because the rates were all
    #: measured at today's volume.
    assumptions: list[str]
    #: What ATLAS is not in a position to answer at all.
    out_of_scope: list[str]
