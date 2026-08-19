import enum


class LifecycleState(enum.StrEnum):
    """States an agent moves through after onboarding."""

    ONBOARDING = "onboarding"
    HEALTHY = "healthy"
    ANOMALY = "anomaly"
    REVIEW = "review"
    RECOVERY = "recovery"
    TRUSTED = "trusted"


class DecisionOutcome(enum.StrEnum):
    APPROVED = "approved"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


class Severity(enum.StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ActivityTone(enum.StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
