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


class Role(enum.StrEnum):
    """Access level, ordered least to most privileged.

    Deliberately coarse. Fine-grained permissions invite a matrix nobody can
    reason about, and the question this system has to answer at review time is
    "who could have committed this decision?" — which needs an answer short
    enough to fit in a sentence.
    """

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


#: Privilege ordering. A separate mapping rather than enum order, because
#: relying on declaration order for a security check is the kind of thing that
#: breaks silently when someone alphabetises the class.
ROLE_RANK: dict[Role, int] = {
    Role.VIEWER: 0,
    Role.OPERATOR: 1,
    Role.ADMIN: 2,
}


class ActivityTone(enum.StrEnum):
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
