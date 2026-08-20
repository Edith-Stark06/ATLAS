"""The pre-ML heuristics, reused here so the trained models can be scored
against the exact thing they are meant to improve on.

These are deliberately re-implemented rather than imported from
`app.services.trust_engine` — the training pipeline should stay runnable
without a database/app import chain, and duplication of a five-line formula
is cheaper than that coupling.
"""

import numpy as np
import pandas as pd

#: Same weights as app.services.trust_engine.FACTOR_WEIGHTS / app/seed.py —
#: the hand-set baseline this project shipped with in Phase 3.
BASELINE_WEIGHTS = {
    "behavior": 0.22,
    "policy": 0.24,
    "risk": 0.20,
    "context": 0.14,
    "history": 0.20,
}

#: Same threshold as trust_engine.DRIFT_THRESHOLD.
BASELINE_DRIFT_THRESHOLD = -5.0


def baseline_trust_score(df: pd.DataFrame) -> np.ndarray:
    """The hand-set weighted mean — higher means more trustworthy."""
    total_weight = sum(BASELINE_WEIGHTS.values())
    score = np.zeros(len(df))
    for key, weight in BASELINE_WEIGHTS.items():
        score += df[f"factor_{key}"].to_numpy() * weight
    return score / total_weight


def baseline_risk_of_adverse(df: pd.DataFrame) -> np.ndarray:
    """Baseline score cast as a risk-of-adverse-outcome estimate, so it is
    directly comparable to the trained model's predicted probability (both
    are "higher = more likely to go wrong")."""
    return 100.0 - baseline_trust_score(df)


def baseline_drift_flags(latent_scores: pd.Series, window: int = 8) -> np.ndarray:
    """The Phase 3 drift heuristic: current score vs. mean of the trailing
    window, flagged when the drop exceeds a fixed threshold — applied here
    per-agent over a synthetic timeline for evaluation against the injected
    ground-truth drift events.
    """
    values = latent_scores.to_numpy()
    flags = np.zeros(len(values), dtype=bool)
    for i in range(len(values)):
        history = values[max(0, i - window) : i]
        if len(history) == 0:
            continue
        baseline = history.mean()
        flags[i] = (values[i] - baseline) <= BASELINE_DRIFT_THRESHOLD
    return flags


def composite_factor_score(df: pd.DataFrame) -> pd.Series:
    """0–100 composite used as the "current score" input to drift flagging —
    equivalent to what `Agent.trust_score` would hold at each step."""
    return pd.Series(baseline_trust_score(df), index=df.index)
