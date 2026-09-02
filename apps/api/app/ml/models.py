"""Loads trained artifacts for use at request time.

Loading is lazy and cached — the API must start and serve traffic even if
`python -m app.ml.train` has never been run (fresh clone, CI, a reviewer
checking out the repo). Every caller in app.services checks `is_available`
and falls back to the Phase 3 heuristic rather than raising.
"""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib
import numpy as np
import shap
from sklearn.ensemble import IsolationForest

from app.ml.dataset import FACTOR_KEYS
from app.ml.train import ARTIFACTS_DIR, SIMULATION_FEATURES

#: Matches the contamination the training pipeline found effective for this
#: dataset (metrics.json: anomaly_detection.contamination_used) — there is
#: no per-agent ground truth to tune against at request time, so this is a
#: fixed operating point rather than an estimate.
RUNTIME_ANOMALY_CONTAMINATION = 0.12

#: Fewer points than this and an Isolation Forest has nothing to isolate
#: against — fall back to "not enough history yet" rather than a fit that
#: cannot mean anything on 2–3 samples.
MIN_HISTORY_FOR_ANOMALY = 6


@dataclass(frozen=True)
class TrustPrediction:
    #: 0-100, higher is more trustworthy — 100 * (1 - P(next decision adverse)).
    score: float
    #: Per-factor contribution to this specific prediction, same units as score.
    attribution: dict[str, float]


class TrustModel:
    def __init__(self, model, scaler, explainer):
        self._model = model
        self._scaler = scaler
        self._explainer = explainer

    def predict(self, factors: dict[str, float]) -> TrustPrediction:
        x = np.array([[factors[k] for k in FACTOR_KEYS]])
        x_scaled = self._scaler.transform(x)

        p_adverse = float(self._model.predict_proba(x_scaled)[0, 1])
        score = 100.0 * (1.0 - p_adverse)

        # SHAP values are in probability-of-adverse space; negate and rescale
        # to score space so a positive attribution reads as "helped trust".
        shap_row = np.asarray(self._explainer.shap_values(x_scaled))[0]
        attribution = {
            key: round(float(-shap_row[i] * 100), 2) for i, key in enumerate(FACTOR_KEYS)
        }
        return TrustPrediction(score=round(score, 2), attribution=attribution)

    def top_k_indices(self, k: int = 2) -> np.ndarray:
        """Indices of the k factors with the largest |learned weight| — used
        to feed the anomaly detector only the informative dimensions."""
        importance = np.abs(self._model.coef_[0])
        return np.argsort(importance)[::-1][:k]

    def detect_anomaly(self, history: list[dict[str, float]]) -> tuple[bool, float] | None:
        """Is the *last* entry in `history` anomalous relative to the rest?

        Fits fresh on this call — this is the "per-agent, judged only
        against its own accumulated behaviour" mechanism validated in
        app.ml.train.evaluate_anomaly_detection, applied to one agent's real
        stored history instead of a synthetic evaluation set. Feature
        selection (top_k_indices) matters here for the same reason it did in
        training: Isolation Forest picks split features uniformly at random,
        so unweighted noisy dimensions measurably degrade what it can isolate.
        """
        if len(history) < MIN_HISTORY_FOR_ANOMALY:
            return None

        indices = self.top_k_indices(2)
        keys = [FACTOR_KEYS[i] for i in indices]
        if any(key not in row for row in history for key in keys):
            return None

        x = np.array([[row[key] for key in keys] for row in history])
        forest = IsolationForest(
            n_estimators=100, contamination=RUNTIME_ANOMALY_CONTAMINATION, random_state=0
        )
        forest.fit(x)
        is_anomaly = bool(forest.predict(x)[-1] == -1)
        score = float(forest.decision_function(x)[-1])
        return is_anomaly, score


class SimulationModel:
    def __init__(self, model):
        self._model = model

    def predict_outcomes(self, features: dict[str, float]) -> list[dict]:
        x = np.array([[features[k] for k in SIMULATION_FEATURES]])
        proba = self._model.predict_proba(x)[0]
        return [
            {"outcome": cls, "probability": round(float(p), 4)}
            for cls, p in zip(self._model.classes_, proba, strict=True)
        ]


class RiskModel:
    """Trained on real transaction data (app.ml.train_risk_model), not the
    synthetic generator the other two models use — see
    docs/patent/technical-disclosure.md §5.9. Predicts a real fraud
    probability from real transaction features (amount, hour, and the
    dataset's 28 anonymized behavioural components); has no notion of
    governance context, unlike SimulationModel."""

    def __init__(self, model):
        self._model = model

    def predict_risk_score(self, features: dict[str, float]) -> float:
        """0-100, higher is riskier — 100 * P(fraud), same scale and
        direction as every other risk_score in this codebase."""
        from app.ml.real_data import RISK_MODEL_FEATURES

        x = np.array([[features[k] for k in RISK_MODEL_FEATURES]])
        p_fraud = float(self._model.predict_proba(x)[0, 1])
        return round(100.0 * p_fraud, 2)


@lru_cache(maxsize=1)
def load_trust_model() -> TrustModel | None:
    model_path = ARTIFACTS_DIR / "trust_model.joblib"
    scaler_path = ARTIFACTS_DIR / "trust_scaler.joblib"
    if not (model_path.exists() and scaler_path.exists()):
        return None

    model = joblib.load(model_path)
    scaler = joblib.load(scaler_path)
    # The model was fit on scaler.transform(x) — scaled feature space, mean 0
    # by construction. The explainer's background must be in that same
    # space, not raw factor units, or shap_values comes out orders of
    # magnitude wrong (the model's coefficients apply to standardised units).
    explainer = shap.LinearExplainer(model, np.zeros((1, len(FACTOR_KEYS))))
    return TrustModel(model, scaler, explainer)


@lru_cache(maxsize=1)
def load_simulation_model() -> SimulationModel | None:
    model_path = ARTIFACTS_DIR / "simulation_model.joblib"
    if not model_path.exists():
        return None
    return SimulationModel(joblib.load(model_path))


@lru_cache(maxsize=1)
def load_risk_model() -> RiskModel | None:
    model_path = ARTIFACTS_DIR / "risk_model.joblib"
    if not model_path.exists():
        return None
    return RiskModel(joblib.load(model_path))


def clear_caches() -> None:
    """Drop every cached loader so the next call re-reads whatever's on disk
    now, instead of whatever was there when the process started.

    Swapping files on disk (app.ml.promote) does nothing on its own — every
    loader here is `@lru_cache(maxsize=1)`, cached for the process's whole
    life, which is exactly why: re-reading several megabytes of joblib per
    request would put disk I/O in the hot path. `POST /trust/reload-models`
    is the only thing that calls this — a promotion takes effect on a
    running process only once something explicitly asks for it, not the
    instant new bytes land on disk.
    """
    load_trust_model.cache_clear()
    load_simulation_model.cache_clear()
    load_risk_model.cache_clear()


def load_metrics() -> dict | None:
    """The train/baseline comparison report — used to show model provenance
    and evaluation results in the console rather than asserting them blind."""
    import json

    metrics_path = ARTIFACTS_DIR / "metrics.json"
    if not metrics_path.exists():
        return None
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def artifacts_dir() -> Path:
    return ARTIFACTS_DIR
