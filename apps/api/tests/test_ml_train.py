"""Tests for the training pipeline itself — that it runs, and that the
baseline-vs-learned comparison it produces is at least directionally sound.
Uses a small synthetic config so this stays fast; the real evaluation
numbers quoted in the technical disclosure come from the full run via
`python -m app.ml.train`, saved to app/ml/artifacts/metrics.json.
"""

import numpy as np

from app.ml.dataset import (
    DatasetConfig,
    build_simulation_training_frame,
    build_trust_training_frame,
    generate_agent_timelines,
    train_test_split_by_agent,
)
from app.ml.train import (
    evaluate_anomaly_detection,
    train_simulation_model,
    train_trust_model,
)

#: Small but large enough for logistic regression and Isolation Forest to
#: find real structure rather than fitting noise.
CONFIG = DatasetConfig(n_agents=80, n_steps=50, seed=11)


def _trust_split():
    timelines = generate_agent_timelines(CONFIG)
    frame = build_trust_training_frame(timelines)
    return train_test_split_by_agent(frame, seed=2)


def test_trust_model_beats_baseline():
    """The whole point of the exercise: a model fit to labelled outcomes
    should out-rank a hand-set formula that does not match the (deliberately
    different) true generative weights. See dataset.TRUE_OUTCOME_WEIGHTS."""
    train, test = _trust_split()
    _, _, metrics = train_trust_model(train, test)

    assert metrics["learned_auc"] > metrics["baseline_auc"]
    assert 0.5 < metrics["baseline_auc"] < 1.0
    assert 0.5 < metrics["learned_auc"] <= 1.0


def test_trust_model_recovers_the_dominant_true_factors():
    """The fitted coefficients should rank policy and risk (the two
    dominant factors in TRUE_OUTCOME_WEIGHTS) above the three that are
    mostly noise — the model has no access to TRUE_OUTCOME_WEIGHTS, so this
    only holds if it is genuinely learning from the labels."""
    train, test = _trust_split()
    _, _, metrics = train_trust_model(train, test)

    coefs = {k: abs(v) for k, v in metrics["learned_coefficients"].items()}
    dominant = max(coefs["policy"], coefs["risk"])
    weak = max(coefs["behavior"], coefs["context"], coefs["history"])
    assert dominant > weak


def test_simulation_model_beats_the_fixed_percentage_baseline():
    """Log-loss, not accuracy, is the claim that matters here: the
    Simulation Engine surfaces *probabilities* ("64% human review"), so what
    must improve is calibration, not just the argmax class. Raw accuracy can
    be a noisy, near-tied metric on an imbalanced label at this sample size
    even when the learned probabilities are genuinely better calibrated."""
    timelines = generate_agent_timelines(CONFIG)
    frame = build_simulation_training_frame(timelines)
    train, test = train_test_split_by_agent(frame, seed=3)

    _, metrics = train_simulation_model(train, test)

    assert metrics["learned_log_loss"] < metrics["baseline_log_loss"]


def test_anomaly_detection_reports_precision_and_recall_for_both_arms():
    timelines = generate_agent_timelines(CONFIG)
    _, test_timelines = train_test_split_by_agent(timelines, seed=4)

    metrics = evaluate_anomaly_detection(
        test_timelines,
        contamination=0.1,
        feature_weights=np.array([0.1, 0.4, 0.4, 0.05, 0.05]),
    )

    for arm in ("baseline", "learned"):
        for key in ("precision", "recall", "f1"):
            assert 0.0 <= metrics[arm][key] <= 1.0
    assert metrics["n_drift_steps"] > 0
