"""The Trust Engine.

Computes an agent's trust score from its weighted factors, penalises recent
adverse outcomes, detects behavioural drift against the agent's own history,
and derives the lifecycle state that follows.

Every number produced here is traceable to stored data — factor scores and
recorded decisions. Nothing is invented; where there is insufficient history
to answer (notably forecasting), the answer is `None` rather than a guess.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.models import Agent, Decision, TrustSnapshot
from app.models.enums import DecisionOutcome, LifecycleState

# --- Tunables ---------------------------------------------------------------

#: How far back adverse decisions count against an agent.
ANOMALY_WINDOW = timedelta(days=7)

#: Points deducted per adverse decision in the window.
PENALTY_PER_BLOCKED = 3.0
PENALTY_PER_ESCALATED = 1.5
#: A run of bad decisions should hurt, but not erase an otherwise strong record.
MAX_ANOMALY_PENALTY = 20.0

#: Drop (in points) against the historical baseline that counts as drift.
DRIFT_THRESHOLD = -5.0
#: A steeper drop moves the agent to ANOMALY rather than merely flagging drift.
ANOMALY_DRIFT_THRESHOLD = -10.0

#: Score bands.
TRUSTED_MIN = 90
HEALTHY_MIN = 75
REVIEW_BELOW = 60

#: An agent stays in onboarding until it has enough decisions to judge.
ONBOARDING_MIN_DECISIONS = 500

#: Fewest snapshots before a forecast is meaningful.
MIN_FORECAST_SAMPLES = 3

#: Baseline excludes the most recent snapshots so drift compares "now" to "before".
BASELINE_EXCLUDE_RECENT = 1

#: The five factors compute_base_score weighs, and their canonical labels
#: and weights — every agent, seeded or newly registered, is scored on the
#: same five signals so a composite trust score means the same thing across
#: the whole estate. Weights need not sum to 1 (compute_base_score
#: normalises), but keep them here in one place regardless: two agents
#: scored on different implied weightings would not be comparable, which
#: defeats the purpose of a shared trust score at all.
FACTOR_LABELS = {
    "behavior": "Behavior Consistency",
    "policy": "Policy Compliance",
    "risk": "Risk Exposure",
    "context": "Context Awareness",
    "history": "Historical Reliability",
}
FACTOR_WEIGHTS = {"behavior": 0.22, "policy": 0.24, "risk": 0.20, "context": 0.14, "history": 0.20}


@dataclass(frozen=True)
class DriftAssessment:
    detected: bool
    #: current score minus the historical baseline, in points.
    delta: float
    baseline: float | None
    samples: int


@dataclass(frozen=True)
class TrustEvaluation:
    score: int
    base_score: float
    anomaly_penalty: float
    factors: list[dict]
    lifecycle: LifecycleState
    drift: DriftAssessment
    #: Human-readable account of how the score was reached.
    explanation: list[str]
    #: "ml" when a trained model produced `score`, "heuristic" when it fell
    #: back to the weighted-mean-minus-penalty formula (no model artifact
    #: present, e.g. a fresh clone before `python -m app.ml.train` has run).
    score_source: str = "heuristic"
    #: Per-factor contribution to `score` in score units, from the trained
    #: model's SHAP values — None when score_source is "heuristic", since
    #: the heuristic's own weighted terms already serve that purpose.
    ml_attribution: dict[str, float] | None = None


def compute_base_score(factors) -> float:
    """Weighted mean of the trust factors.

    Weights need not sum to 1 — they are normalised here so adding a factor
    does not silently rescale every agent's score.
    """
    total_weight = sum(f.weight for f in factors)
    if not factors or total_weight <= 0:
        return 0.0
    return sum(f.score * f.weight for f in factors) / total_weight


def compute_anomaly_penalty(
    decisions: list[Decision], *, now: datetime | None = None
) -> tuple[float, int, int]:
    """Penalty for adverse decisions inside the anomaly window.

    Returns (penalty, blocked_count, escalated_count).
    """
    now = now or datetime.now(UTC)
    cutoff = now - ANOMALY_WINDOW

    blocked = 0
    escalated = 0
    for decision in decisions:
        if decision.decided_at < cutoff:
            continue
        if decision.outcome == DecisionOutcome.BLOCKED:
            blocked += 1
        elif decision.outcome == DecisionOutcome.ESCALATED:
            escalated += 1

    raw = blocked * PENALTY_PER_BLOCKED + escalated * PENALTY_PER_ESCALATED
    return min(raw, MAX_ANOMALY_PENALTY), blocked, escalated


def assess_drift(current: float, snapshots: list[TrustSnapshot]) -> DriftAssessment:
    """Compare the current score against this agent's own recent history.

    Comparing an agent to itself is what makes drift meaningful; comparing
    across agents would only measure that they are different agents.
    """
    history = snapshots[:-BASELINE_EXCLUDE_RECENT] if BASELINE_EXCLUDE_RECENT else snapshots
    if not history:
        return DriftAssessment(detected=False, delta=0.0, baseline=None, samples=0)

    baseline = sum(s.score for s in history) / len(history)
    delta = current - baseline
    return DriftAssessment(
        detected=delta <= DRIFT_THRESHOLD,
        delta=round(delta, 2),
        baseline=round(baseline, 2),
        samples=len(history),
    )


def next_lifecycle(
    *,
    score: int,
    previous: LifecycleState,
    drift: DriftAssessment,
    decision_volume: int,
) -> LifecycleState:
    """Derive the lifecycle state implied by the current evaluation.

    Order matters: an agent that is drifting badly is an ANOMALY even if its
    absolute score still looks respectable, and an agent climbing out of
    trouble passes through RECOVERY before it is trusted again.

    `decision_volume` is the agent's operational throughput, not the number of
    decisions ATLAS has stored in detail — the ledger keeps full records only
    for notable decisions, so counting rows would strand every agent in
    onboarding forever.
    """
    if decision_volume < ONBOARDING_MIN_DECISIONS:
        return LifecycleState.ONBOARDING

    if score < REVIEW_BELOW:
        return LifecycleState.REVIEW

    if drift.detected and drift.delta <= ANOMALY_DRIFT_THRESHOLD:
        return LifecycleState.ANOMALY

    if previous in (LifecycleState.REVIEW, LifecycleState.ANOMALY) and drift.delta > 0:
        return LifecycleState.RECOVERY

    if drift.detected:
        return LifecycleState.ANOMALY

    if score >= TRUSTED_MIN:
        return LifecycleState.TRUSTED

    if score >= HEALTHY_MIN:
        return LifecycleState.HEALTHY

    return LifecycleState.REVIEW


def forecast(snapshots: list[TrustSnapshot]) -> int | None:
    """Project an agent's next score from its own snapshot history."""
    return forecast_series([float(s.score) for s in snapshots])


def forecast_series(scores: list[float]) -> int | None:
    """Project the next value by least-squares slope over an ordered series.

    Returns None below MIN_FORECAST_SAMPLES — a trend line through two points
    is not a forecast, and inventing one would misrepresent confidence.

    The caller is responsible for passing a series that means something: this
    is only valid over repeated measurements of the *same* subject.
    """
    if len(scores) < MIN_FORECAST_SAMPLES:
        return None

    n = len(scores)
    mean_x = (n - 1) / 2
    mean_y = sum(scores) / n

    denominator = sum((i - mean_x) ** 2 for i in range(n))
    if denominator == 0:
        return int(round(mean_y))

    slope = sum((i - mean_x) * (y - mean_y) for i, y in enumerate(scores)) / denominator
    projected = scores[-1] + slope
    return int(round(max(0.0, min(100.0, projected))))


def evaluate(
    agent: Agent,
    decisions: list[Decision],
    snapshots: list[TrustSnapshot],
    *,
    now: datetime | None = None,
    ml_score: float | None = None,
    ml_attribution: dict[str, float] | None = None,
) -> TrustEvaluation:
    """Run a full trust evaluation for one agent.

    `ml_score`/`ml_attribution` come from a trained model (see
    app.ml.models.TrustModel), loaded and computed by the caller — this
    function has no knowledge of sklearn/joblib and stays testable with
    plain objects. When ml_score is None (no trained artifact on disk), the
    heuristic weighted-mean-minus-penalty formula is used instead, and is
    always computed regardless, purely as a documented point of comparison
    in the explanation.
    """
    base = compute_base_score(agent.factors)
    penalty, blocked, escalated = compute_anomaly_penalty(decisions, now=now)
    heuristic_score = int(round(max(0.0, min(100.0, base - penalty))))

    if ml_score is not None:
        score = int(round(max(0.0, min(100.0, ml_score))))
        score_source = "ml"
    else:
        score = heuristic_score
        score_source = "heuristic"

    drift = assess_drift(score, snapshots)
    lifecycle = next_lifecycle(
        score=score,
        previous=agent.lifecycle,
        drift=drift,
        decision_volume=agent.decisions_today,
    )

    explanation = []
    if ml_score is not None:
        explanation.append(
            f"ML score: {score} (trained logistic regression, calibrated probability of "
            f"compliant behaviour)"
        )
        explanation.append(
            f"Heuristic score for comparison: {heuristic_score} "
            f"(weighted factor mean {base:.1f} − penalty {penalty:.1f})"
        )
    else:
        explanation.append(f"Weighted factor mean: {base:.1f}")
    penalty_prefix = "Heuristic penalty" if ml_score is not None else "Anomaly penalty"
    if penalty:
        parts = []
        if blocked:
            parts.append(f"{blocked} blocked")
        if escalated:
            parts.append(f"{escalated} escalated")
        explanation.append(
            f"{penalty_prefix} −{penalty:.1f} from {' and '.join(parts)} "
            f"in the last {ANOMALY_WINDOW.days} days"
        )
    else:
        explanation.append("No adverse decisions in the anomaly window")

    if drift.baseline is None:
        explanation.append("No prior history to compare against")
    elif drift.detected:
        explanation.append(
            f"Drift detected: {drift.delta:+.1f} against a baseline of "
            f"{drift.baseline:.1f} over {drift.samples} snapshots"
        )
    else:
        explanation.append(f"Stable: {drift.delta:+.1f} against a baseline of {drift.baseline:.1f}")

    explanation.append(f"Lifecycle: {agent.lifecycle.value} → {lifecycle.value}")

    return TrustEvaluation(
        score=score,
        base_score=round(base, 2),
        anomaly_penalty=round(penalty, 2),
        factors=[
            {"key": f.key, "label": f.label, "score": f.score, "weight": f.weight}
            for f in agent.factors
        ],
        lifecycle=lifecycle,
        drift=drift,
        explanation=explanation,
        score_source=score_source,
        ml_attribution=ml_attribution,
    )
