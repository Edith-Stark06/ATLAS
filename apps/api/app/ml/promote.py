"""Promotes a candidate model artifact set to live, after comparing its
metrics against the current live set — never blind.

A candidate is built by `python -m app.ml.train --output-dir <path>`
and/or `python -m app.ml.train_risk_model --output-dir <path>` (a `--seed`
override on either is what makes a candidate genuinely different from live
to compare, since training data is otherwise deterministic).

    python -m app.ml.promote <candidate-dir>
    python -m app.ml.promote <candidate-dir> --force --reason "..."
    python -m app.ml.promote --rollback <backup-dir>

There is no live traffic-split canary here — that needs infrastructure
(weighted routing across replicas) this project doesn't have. What this
gives instead: a candidate is evaluated against the same held-out metrics
this project already computes and reports before it ever becomes live, and
promotion is refused if any of them regressed past tolerance unless
explicitly forced with a reason. That serves the same risk-reduction goal
(don't ship a worse model) a canary does, without infrastructure this
project can't support yet.
"""

import argparse
import json
import os
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from app.ml.train import ARTIFACTS_DIR

#: (dotted path in metrics.json, direction, human label) for every metric
#: this project already computes and reports (technical-disclosure.md §6).
#: Only metrics present in *both* live and candidate are compared — a
#: candidate that only retrained the trust model isn't penalised for a risk
#: model it never touched.
_METRIC_SPECS: list[tuple[str, str, str]] = [
    ("trust_model.learned_auc", "higher_better", "trust AUC"),
    ("anomaly_detection.learned.f1", "higher_better", "anomaly F1"),
    ("simulation_model.learned_log_loss", "lower_better", "simulation log-loss"),
    (
        "real_data_risk_model.learned_average_precision",
        "higher_better",
        "risk model average precision",
    ),
]

#: How much a metric may regress before promotion is refused without --force.
#: A single fixed tolerance across differently-scaled metrics (AUC vs.
#: log-loss) is a simplification, not a claim of statistical rigor — it
#: exists to catch an obviously worse candidate, not to replace judgment.
TOLERANCE = 0.02


@dataclass(frozen=True)
class MetricDelta:
    path: str
    label: str
    direction: str
    live: float
    candidate: float
    regressed: bool


@dataclass(frozen=True)
class ComparisonResult:
    deltas: list[MetricDelta]
    regressed: list[MetricDelta]

    @property
    def clean(self) -> bool:
        return not self.regressed


def _get(metrics: dict, dotted_path: str) -> float | None:
    value: object = metrics
    for part in dotted_path.split("."):
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value if isinstance(value, int | float) else None


def compare(live_metrics: dict, candidate_metrics: dict) -> ComparisonResult:
    """Every metric present in both sets, direction-aware — never invents a
    comparison for a metric one side doesn't have."""
    deltas = []
    for path, direction, label in _METRIC_SPECS:
        live_value = _get(live_metrics, path)
        candidate_value = _get(candidate_metrics, path)
        if live_value is None or candidate_value is None:
            continue

        if direction == "higher_better":
            regressed = candidate_value < live_value - TOLERANCE
        else:
            regressed = candidate_value > live_value + TOLERANCE

        deltas.append(MetricDelta(path, label, direction, live_value, candidate_value, regressed))

    return ComparisonResult(deltas=deltas, regressed=[d for d in deltas if d.regressed])


def promote(candidate_dir: Path, *, artifacts_dir: Path = ARTIFACTS_DIR) -> Path:
    """Overlay `candidate_dir` onto the live artifact set.

    Deliberately an overlay, not a wholesale directory swap — caught by
    actually running this against the real live artifacts during
    verification, not assumed safe from reading the code: a candidate that
    only retrained one model (`python -m app.ml.train`, without also
    running `train_risk_model.py`) has no `risk_model.joblib` at all, and a
    plain "replace the directory" would silently delete the live one, along
    with anything else the candidate never touched. Promotion instead
    starts every file from a full backup of what was live, then overlays
    only what the candidate actually produced.

    `metrics.json` gets the same per-top-level-key merge `train.py`/
    `train_risk_model.py` already do internally, for the same reason: a
    trust-only candidate's fresh metrics.json has no `real_data_risk_model`
    section, and copying it over verbatim would erase that section's
    history even though `risk_model.joblib` itself is preserved by the
    file-level overlay above.

    Not a single atomic operation — `os.replace` on the live directory
    (into a timestamped backup, which doubles as rollback's source) is
    atomic on its own, but the overlay that follows is a series of file
    copies, so there is a real window where the live directory is
    incomplete. Stated plainly rather than claimed otherwise: a true
    all-or-nothing swap needs a symlink indirection, which is permission-
    gated on Windows and not worth that friction for what is still a large,
    correctness-checked improvement over the direct, unguarded overwrite
    this replaces. Returns the backup directory so a caller can roll back
    immediately if something looks wrong after reload.
    """
    backup_dir = artifacts_dir.parent / f"artifacts.backup.{int(time.time())}"
    if artifacts_dir.exists():
        os.replace(artifacts_dir, backup_dir)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    for source_dir in (backup_dir, candidate_dir):
        if not source_dir.exists():
            continue
        for item in source_dir.iterdir():
            if item.name != "metrics.json":
                shutil.copy2(item, artifacts_dir / item.name)

    merged_metrics = {**_load_metrics(backup_dir), **_load_metrics(candidate_dir)}
    (artifacts_dir / "metrics.json").write_text(
        json.dumps(merged_metrics, indent=2), encoding="utf-8"
    )

    # Copied, not moved (the overlay above needs candidate_dir to still
    # exist while backup_dir's older files are being copied in first) — so
    # it's cleaned up explicitly now that everything from it has landed in
    # artifacts_dir, rather than left behind as an orphaned scratch dir.
    shutil.rmtree(candidate_dir, ignore_errors=True)

    return backup_dir


def rollback(backup_dir: Path, *, artifacts_dir: Path = ARTIFACTS_DIR) -> Path:
    """The reverse of promote — reuses the backup promote already made.
    Returns the directory the (bad) live set was moved to, in case that's
    needed too."""
    discarded_dir = artifacts_dir.parent / f"artifacts.discarded.{int(time.time())}"
    if artifacts_dir.exists():
        os.replace(artifacts_dir, discarded_dir)
    os.replace(backup_dir, artifacts_dir)
    return discarded_dir


def _load_metrics(directory: Path) -> dict:
    path = directory / "metrics.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    args = _parse_args()

    if args.rollback is not None:
        discarded = rollback(args.rollback, artifacts_dir=args.artifacts_dir)
        print(f"Rolled back. The set that was live is now at {discarded}")
        return

    live_metrics = _load_metrics(args.artifacts_dir)
    candidate_metrics = _load_metrics(args.candidate_dir)
    if not candidate_metrics:
        raise SystemExit(f"No metrics.json found in candidate directory {args.candidate_dir}")

    comparison = compare(live_metrics, candidate_metrics)
    print("Metric comparison (live -> candidate):")
    for delta in comparison.deltas:
        flag = " REGRESSED" if delta.regressed else ""
        print(f"  {delta.label}: {delta.live:.4f} -> {delta.candidate:.4f}{flag}")
    if not comparison.deltas:
        print("  (no comparable metrics found in both live and candidate)")

    if comparison.regressed and not args.force:
        print(
            f"\nRefusing to promote — {len(comparison.regressed)} metric(s) "
            "regressed beyond tolerance."
        )
        print('Re-run with --force --reason "..." to promote anyway.')
        raise SystemExit(1)

    if comparison.regressed:
        print(f"\nForced promotion despite regression. Reason: {args.reason}")

    backup_dir = promote(args.candidate_dir, artifacts_dir=args.artifacts_dir)
    print(f"\nPromoted. Previous live artifacts backed up to {backup_dir}")
    print("Call POST /trust/reload-models on a running server to pick this up without a restart.")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "candidate_dir", type=Path, nargs="?", help="Candidate artifact directory to promote"
    )
    parser.add_argument(
        "--rollback",
        type=Path,
        default=None,
        metavar="BACKUP_DIR",
        help="Restore a previous backup instead of promoting",
    )
    parser.add_argument(
        "--force", action="store_true", help="Promote even if a metric regressed beyond tolerance"
    )
    parser.add_argument(
        "--reason",
        default="",
        help="Required with --force — context for the forced promotion, printed for accountability",
    )
    parser.add_argument(
        "--artifacts-dir",
        type=Path,
        default=ARTIFACTS_DIR,
        help="Live artifacts directory (default: app/ml/artifacts/)",
    )
    args = parser.parse_args()

    if args.rollback is None and args.candidate_dir is None:
        parser.error("candidate_dir is required unless --rollback is given")
    if args.force and not args.reason:
        parser.error("--force requires --reason")
    return args


if __name__ == "__main__":
    main()
