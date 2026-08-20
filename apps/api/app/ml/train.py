"""Train the ML Trust Engine's three models and evaluate each against the
Phase 3 heuristic it replaces.

Run with `python -m app.ml.train`. Writes model artifacts to
`app/ml/artifacts/` and a metrics.json documenting the baseline-vs-learned
comparison — this is the quantitative "technical effect" evidence for the
patent's technical disclosure, not just a build log.

No database access — this trains purely on the synthetic dataset in
app.ml.dataset, so it is runnable in any environment with the ML deps
installed, independent of Postgres being up.
"""

import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, IsolationForest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

from app.ml import baseline
from app.ml.dataset import (
    FACTOR_KEYS,
    DatasetConfig,
    build_simulation_training_frame,
    build_trust_training_frame,
    generate_agent_timelines,
    train_test_split_by_agent,
)

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"

SIMULATION_FEATURES = [
    "risk_score",
    "log_amount",
    "hour",
    "policy_pass_rate",
    "trust_proxy",
    "authority_level",
]
SIMULATION_CLASSES = ["approved", "escalated", "blocked"]


def _factor_matrix(df) -> np.ndarray:
    return df[[f"factor_{k}" for k in FACTOR_KEYS]].to_numpy()


def train_trust_model(train_df, test_df) -> tuple[LogisticRegression, StandardScaler, dict]:
    """Logistic regression over the five trust factors, predicting the
    probability that the agent's next decision is adverse.

    Logistic regression rather than a black-box model: its coefficients ARE
    the learned factor weights, so the model stays exactly as interpretable
    as the hand-set formula it replaces — just no longer hand-set. This also
    keeps SHAP explanation exact rather than approximate.
    """
    x_train = _factor_matrix(train_df)
    y_train = train_df["label_adverse"].to_numpy()
    x_test = _factor_matrix(test_df)
    y_test = test_df["label_adverse"].to_numpy()

    scaler = StandardScaler().fit(x_train)
    model = LogisticRegression(max_iter=1000, C=1.0)
    model.fit(scaler.transform(x_train), y_train)

    learned_proba = model.predict_proba(scaler.transform(x_test))[:, 1]
    baseline_risk = baseline.baseline_risk_of_adverse(test_df) / 100.0

    metrics = {
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "baseline_auc": float(roc_auc_score(y_test, baseline_risk)),
        "learned_auc": float(roc_auc_score(y_test, learned_proba)),
        "learned_coefficients": dict(zip(FACTOR_KEYS, model.coef_[0].tolist(), strict=True)),
    }
    metrics["auc_improvement_pct"] = round(
        100 * (metrics["learned_auc"] - metrics["baseline_auc"]) / metrics["baseline_auc"], 1
    )
    return model, scaler, metrics


def evaluate_anomaly_detection(
    test_timelines, *, contamination: float, feature_weights: np.ndarray, top_k: int = 2
) -> dict:
    """Per-agent Isolation Forest, fit on that agent's own factor-vector
    history and scored against the same history, versus the Phase 3 static
    mean-baseline-and-threshold heuristic.

    Fitting per agent (rather than one global model) is deliberate: it is
    the technical mechanism being evaluated, not just an implementation
    detail — each agent is judged only against its own accumulated
    behaviour, which is what makes the comparison to a population-wide
    threshold meaningful.

    `feature_weights` (the trust model's own learned |coefficients|, see
    main()) selects the `top_k` factors the forest is fit on. This is
    feature *selection*, not rescaling — Isolation Forest picks a split
    feature uniformly at random at every node regardless of its scale, so
    multiplying a noisy column by a constant changes nothing; only removing
    it does. Fitting on all five raw factors measurably underperforms here:
    three of the five are mostly noise (dataset.FACTOR_SIGNAL_STRENGTH), and
    isolation-based detection degrades exactly as dimensionality of
    irrelevant features grows — the textbook curse-of-dimensionality failure
    mode for this class of method, and the reason the selection step exists.

    `contamination` is estimated from the *training* split's drift rate
    (see main()) — a global prior on how often drift occurs, not the test
    agent's own ground truth, so this stays a fair, non-leaky comparison.
    """
    top_indices = np.argsort(feature_weights)[::-1][:top_k]
    y_true_all, y_pred_learned_all, y_pred_baseline_all = [], [], []

    for _agent_id, group in test_timelines.groupby("agent_id"):
        group = group.sort_values("step")
        x = _factor_matrix(group)[:, top_indices]
        y_true = group["is_drift_event"].to_numpy()

        if len(group) < 10 or y_true.sum() == 0:
            # No injected drift for this agent — nothing to score precision/
            # recall against; skip rather than manufacture a vacuous result.
            continue

        forest = IsolationForest(n_estimators=100, contamination=contamination, random_state=0)
        forest.fit(x)
        learned_flags = forest.predict(x) == -1

        composite = baseline.composite_factor_score(group)
        baseline_flags = baseline.baseline_drift_flags(composite)

        y_true_all.append(y_true)
        y_pred_learned_all.append(learned_flags)
        y_pred_baseline_all.append(baseline_flags)

    y_true = np.concatenate(y_true_all)
    learned = np.concatenate(y_pred_learned_all)
    baseline_pred = np.concatenate(y_pred_baseline_all)

    def _prf(pred):
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, pred, average="binary", zero_division=0
        )
        return {"precision": float(precision), "recall": float(recall), "f1": float(f1)}

    return {
        "n_agents_evaluated": int(len(y_true_all)),
        "n_drift_steps": int(y_true.sum()),
        "baseline": _prf(baseline_pred),
        "learned": _prf(learned),
    }


def train_simulation_model(train_df, test_df) -> tuple[HistGradientBoostingClassifier, dict]:
    """Multi-class outcome classifier: given the features of a decision at
    the moment it is requested, predict approve/escalate/block probabilities.

    This is what makes the Simulation Engine's "predicted futures" real —
    Phase 1/2 rendered fixed percentages (18/64/18) regardless of the
    decision's actual features. The baseline here reproduces exactly that:
    one constant probability vector for every decision, from the training
    set's class frequencies.
    """
    for df in (train_df, test_df):
        df["log_amount"] = np.log1p(df["amount_usd"])

    x_train = train_df[SIMULATION_FEATURES].to_numpy()
    y_train = train_df["outcome"].to_numpy()
    x_test = test_df[SIMULATION_FEATURES].to_numpy()
    y_test = test_df["outcome"].to_numpy()

    # early_stopping="auto" only activates above 10k rows — below that it is
    # silently off, and 200 boosting iterations overfits a small training
    # set into overconfident, badly-calibrated probabilities (log-loss can
    # blow up even when accuracy looks fine). Forcing it on keeps this model
    # robust regardless of how large the synthetic dataset is configured.
    model = HistGradientBoostingClassifier(
        max_iter=200, early_stopping=True, validation_fraction=0.15, random_state=0
    )
    model.fit(x_train, y_train)
    learned_proba = model.predict_proba(x_test)
    learned_pred = model.classes_[np.argmax(learned_proba, axis=1)]

    # Baseline: the same class-frequency vector for every row — exactly the
    # "fixed percentage regardless of input" the seeded fixtures used to do.
    class_order = list(model.classes_)
    priors = train_df["outcome"].value_counts(normalize=True).reindex(class_order).to_numpy()
    baseline_proba = np.tile(priors, (len(x_test), 1))
    baseline_pred = np.full(len(x_test), class_order[int(np.argmax(priors))])

    metrics = {
        "n_train": int(len(train_df)),
        "n_test": int(len(test_df)),
        "classes": class_order,
        "baseline_accuracy": float(accuracy_score(y_test, baseline_pred)),
        "learned_accuracy": float(accuracy_score(y_test, learned_pred)),
        "baseline_log_loss": float(log_loss(y_test, baseline_proba, labels=class_order)),
        "learned_log_loss": float(log_loss(y_test, learned_proba, labels=class_order)),
    }
    return model, metrics


def main() -> None:
    started = time.monotonic()
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

    print("Generating synthetic training data ...")
    timelines = generate_agent_timelines(DatasetConfig())
    trust_frame = build_trust_training_frame(timelines)
    sim_frame = build_simulation_training_frame(timelines)

    trust_train, trust_test = train_test_split_by_agent(trust_frame)
    sim_train, sim_test = train_test_split_by_agent(sim_frame)

    print("Training trust scoring model (logistic regression) ...")
    trust_model, trust_scaler, trust_metrics = train_trust_model(trust_train, trust_test)
    print(
        f"  AUC: baseline={trust_metrics['baseline_auc']:.3f} "
        f"learned={trust_metrics['learned_auc']:.3f} "
        f"({trust_metrics['auc_improvement_pct']:+.1f}%)"
    )

    print("Evaluating per-agent anomaly detection (Isolation Forest) ...")
    anomaly_train_timelines, anomaly_test_timelines = train_test_split_by_agent(timelines)
    # Conditioned on "this agent has at least one drift event" — matching the
    # population evaluate_anomaly_detection actually scores. The unconditional
    # mean is diluted by agents with zero injected drift and understates the
    # true local rate for the agents being evaluated.
    per_agent_drift_rate = anomaly_train_timelines.groupby("agent_id")["is_drift_event"].mean()
    contamination = float(np.clip(per_agent_drift_rate[per_agent_drift_rate > 0].mean(), 0.02, 0.3))
    trust_importance = np.abs(
        np.array([trust_metrics["learned_coefficients"][k] for k in FACTOR_KEYS])
    )
    anomaly_metrics = evaluate_anomaly_detection(
        anomaly_test_timelines, contamination=contamination, feature_weights=trust_importance
    )
    anomaly_metrics["contamination_used"] = contamination
    b, learn = anomaly_metrics["baseline"], anomaly_metrics["learned"]
    print(
        f"  Precision: baseline={b['precision']:.3f} learned={learn['precision']:.3f} | "
        f"Recall: baseline={b['recall']:.3f} learned={learn['recall']:.3f}"
    )

    print("Training simulation outcome model (gradient boosting) ...")
    sim_model, sim_metrics = train_simulation_model(sim_train, sim_test)
    print(
        f"  Accuracy: baseline={sim_metrics['baseline_accuracy']:.3f} "
        f"learned={sim_metrics['learned_accuracy']:.3f} | "
        f"Log-loss: baseline={sim_metrics['baseline_log_loss']:.3f} "
        f"learned={sim_metrics['learned_log_loss']:.3f}"
    )

    joblib.dump(trust_model, ARTIFACTS_DIR / "trust_model.joblib")
    joblib.dump(trust_scaler, ARTIFACTS_DIR / "trust_scaler.joblib")
    joblib.dump(sim_model, ARTIFACTS_DIR / "simulation_model.joblib")

    metrics = {
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(time.monotonic() - started, 1),
        "dataset": {
            "n_agents": DatasetConfig().n_agents,
            "n_steps": DatasetConfig().n_steps,
            "seed": DatasetConfig().seed,
        },
        "trust_model": trust_metrics,
        "anomaly_detection": anomaly_metrics,
        "simulation_model": sim_metrics,
    }
    (ARTIFACTS_DIR / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    print(f"\nArtifacts written to {ARTIFACTS_DIR}")
    print(f"Done in {metrics['duration_seconds']}s")


if __name__ == "__main__":
    main()
