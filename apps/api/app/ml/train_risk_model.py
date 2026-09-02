"""Trains the risk model on real financial transaction data — a genuinely
real dataset, not the synthetic generator the rest of app.ml trains on.

Run with `python -m app.ml.train_risk_model`, after
`python -m app.ml.fetch_real_data`. Writes `risk_model.joblib` to
app/ml/artifacts/ and merges a `real_data_risk_model` section into
metrics.json alongside (not instead of) whatever app.ml.train already wrote
there — see the merge note on `_write_metrics` below.

## What this model is, and isn't

It predicts P(fraud) from a real transaction's amount, hour of day, and 28
real (if individually anonymized) behavioural features, evaluated against
a real, published, independently-verifiable ground truth — genuine
technical-effect evidence for the patent disclosure's §6, not a synthetic
proxy for one.

It is **not** a drop-in replacement for the existing simulation_model
(train.py::train_simulation_model). That model predicts a governance
verdict — approve/escalate/block — from *governance context*
(policy_pass_rate, trust_proxy, authority_level) that has no equivalent in
a transaction dataset; no public dataset could supply those without
fabricating them, which would be exactly the "plausible fabrication" this
project's own design principle rejects (technical-disclosure.md,
PROJECT_MEMORY.md §6). This model instead trains the piece a real dataset
*can* honestly supply: a real risk signal from real transaction features.
See docs/patent/technical-disclosure.md §5.9 for the full scope statement.
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import (
    average_precision_score,
    log_loss,
    precision_recall_fscore_support,
    roc_auc_score,
)

from app.ml.real_data import RISK_MODEL_FEATURES, RealDataSplit, build_risk_training_split

ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
DECISION_THRESHOLD = 0.5


def train_risk_model(split: RealDataSplit) -> tuple[HistGradientBoostingClassifier, dict]:
    """Gradient-boosted classifier over real transaction features, predicting
    real fraud. class_weight="balanced" rather than resampling — resampling
    (SMOTE, undersampling) would synthesize or discard real rows; reweighting
    the loss keeps every real example in the training set exactly once.

    Baseline mirrors train.py::train_simulation_model's: the training set's
    class frequency, predicted for every row regardless of its features —
    the same "fixed percentage regardless of input" standard used throughout
    this project's baseline-vs-learned comparisons (technical-disclosure.md
    §6), applied here to real rather than synthetic data.
    """
    model = HistGradientBoostingClassifier(
        max_iter=200,
        early_stopping=True,
        validation_fraction=0.15,
        class_weight="balanced",
        random_state=0,
    )
    model.fit(split.x_train, split.y_train)

    learned_proba = model.predict_proba(split.x_test)[:, 1]
    learned_pred = (learned_proba >= DECISION_THRESHOLD).astype(int)

    fraud_rate = float(split.y_train.mean())
    baseline_proba = np.full(len(split.x_test), fraud_rate)

    precision, recall, f1, _ = precision_recall_fscore_support(
        split.y_test, learned_pred, average="binary", zero_division=0
    )

    metrics = {
        "n_train": int(len(split.x_train)),
        "n_test": int(len(split.x_test)),
        "n_train_fraud": split.n_train_fraud,
        "n_test_fraud": split.n_test_fraud,
        "train_fraud_rate": fraud_rate,
        "decision_threshold": DECISION_THRESHOLD,
        # ROC-AUC alone reads deceptively well on a 0.17%-positive dataset —
        # average precision (area under the precision-recall curve) is
        # reported alongside it because it doesn't share that distortion.
        "baseline_roc_auc": float(roc_auc_score(split.y_test, baseline_proba)),
        "learned_roc_auc": float(roc_auc_score(split.y_test, learned_proba)),
        "baseline_average_precision": float(average_precision_score(split.y_test, baseline_proba)),
        "learned_average_precision": float(average_precision_score(split.y_test, learned_proba)),
        "baseline_log_loss": float(log_loss(split.y_test, baseline_proba, labels=[0, 1])),
        "learned_log_loss": float(log_loss(split.y_test, learned_proba, labels=[0, 1])),
        f"learned_precision_at_{DECISION_THRESHOLD}": float(precision),
        f"learned_recall_at_{DECISION_THRESHOLD}": float(recall),
        f"learned_f1_at_{DECISION_THRESHOLD}": float(f1),
        # baseline_pred is constant-zero, so precision/recall/F1 for it are
        # undefined-as-zero by construction — reported as such rather than
        # omitted, matching the "an honest gap over a plausible fabrication"
        # standard the rest of this project holds itself to (a baseline that
        # never predicts positive cannot have a precision or recall figure
        # that means anything, and pretending otherwise would misstate it).
        "baseline_precision_recall_f1": "undefined — baseline never predicts positive",
    }
    return model, metrics


def _write_metrics(output_dir: Path, new_section: dict) -> None:
    """Merges into metrics.json rather than overwriting it — app.ml.train and
    this script are independently re-runnable in either order, and each
    writes only its own top-level key. A plain overwrite here would silently
    erase whichever section the *other* script wrote first. (A fresh
    candidate dir never has a prior metrics.json, so this is a no-op merge
    there — same code, no branch needed for the two cases.)
    """
    metrics_path = output_dir / "metrics.json"
    existing = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    existing["real_data_risk_model"] = new_section
    metrics_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")


def main(*, output_dir: Path = ARTIFACTS_DIR, seed: int | None = None) -> None:
    started = time.monotonic()
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Loading real transaction data ...")
    split = build_risk_training_split() if seed is None else build_risk_training_split(seed=seed)
    print(
        f"  {split.x_train.shape[0] + split.x_test.shape[0]} transactions "
        f"({split.n_train_fraud + split.n_test_fraud} labelled fraud)"
    )

    print("Training risk model (gradient boosting on real transactions) ...")
    model, metrics = train_risk_model(split)
    print(
        f"  Average precision: baseline={metrics['baseline_average_precision']:.3f} "
        f"learned={metrics['learned_average_precision']:.3f} | "
        f"ROC-AUC: baseline={metrics['baseline_roc_auc']:.3f} "
        f"learned={metrics['learned_roc_auc']:.3f}"
    )
    print(
        f"  At threshold {DECISION_THRESHOLD}: precision="
        f"{metrics[f'learned_precision_at_{DECISION_THRESHOLD}']:.3f} recall="
        f"{metrics[f'learned_recall_at_{DECISION_THRESHOLD}']:.3f}"
    )

    joblib.dump(model, output_dir / "risk_model.joblib")

    metrics_out = {
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "duration_seconds": round(time.monotonic() - started, 1),
        "dataset": {
            "name": "Credit Card Fraud Detection (Worldline / ULB Machine Learning Group)",
            "source": "https://www.openml.org/d/1597",
            "license": "ODbL v1.0 / DbCL v1.0",
            "real": True,
            "features": RISK_MODEL_FEATURES,
        },
        **metrics,
    }
    _write_metrics(output_dir, metrics_out)

    print(f"\nArtifact written to {output_dir / 'risk_model.joblib'}")
    print(f"Done in {round(time.monotonic() - started, 1)}s")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ARTIFACTS_DIR,
        help="Write the artifact here instead of the live app/ml/artifacts/ "
        "(e.g. a candidate directory for app.ml.promote to review).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Override the train/test split seed (real_data.py default: "
        "20260902) — the underlying data is static and real, so this is "
        "what makes a candidate's split genuinely different to compare.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    main(output_dir=args.output_dir, seed=args.seed)
