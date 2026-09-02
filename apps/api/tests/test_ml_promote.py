"""Tests for the model promotion/rollback mechanism (app/ml/promote.py).

Pure filesystem and metrics-comparison logic — no Postgres, no ML training,
so these stay fast and run even when the DB is unreachable. Real files
under `tmp_path` throughout: the whole point of `promote`/`rollback` is
what they do to a real directory tree, so a mock wouldn't prove much.
"""

import json
import sys
from pathlib import Path

import pytest

from app.ml import promote


def _write_metrics(directory: Path, metrics: dict) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")


# --- compare() -----------------------------------------------------------------


def test_compare_is_clean_when_every_metric_improves():
    live = {"trust_model": {"learned_auc": 0.65}}
    candidate = {"trust_model": {"learned_auc": 0.70}}

    result = promote.compare(live, candidate)

    assert result.clean is True
    assert len(result.deltas) == 1
    assert result.deltas[0].regressed is False


def test_compare_flags_a_metric_that_regressed_beyond_tolerance():
    live = {"trust_model": {"learned_auc": 0.70}}
    candidate = {"trust_model": {"learned_auc": 0.50}}

    result = promote.compare(live, candidate)

    assert result.clean is False
    assert len(result.regressed) == 1
    assert result.regressed[0].label == "trust AUC"


def test_compare_respects_direction_lower_is_better_for_log_loss():
    """A log-loss *increase* is the regression, not a decrease — compare()
    must not treat every metric as "bigger number is better"."""
    live = {"simulation_model": {"learned_log_loss": 0.90}}
    worse = {"simulation_model": {"learned_log_loss": 1.20}}
    better = {"simulation_model": {"learned_log_loss": 0.60}}

    assert promote.compare(live, worse).clean is False
    assert promote.compare(live, better).clean is True


def test_compare_tolerates_a_small_regression_within_tolerance():
    live = {"trust_model": {"learned_auc": 0.700}}
    candidate = {"trust_model": {"learned_auc": 0.695}}  # within TOLERANCE (0.02)

    assert promote.compare(live, candidate).clean is True


def test_compare_ignores_a_metric_missing_from_either_side():
    """A candidate that only retrained the trust model must not be
    penalised for a risk model it never touched."""
    live = {"trust_model": {"learned_auc": 0.70}, "real_data_risk_model": {}}
    candidate = {"trust_model": {"learned_auc": 0.75}}  # no real_data_risk_model at all

    result = promote.compare(live, candidate)

    assert len(result.deltas) == 1
    assert result.deltas[0].label == "trust AUC"


def test_compare_against_an_empty_live_set_finds_nothing_to_compare():
    """A fresh clone / first-ever training run has no live metrics.json at
    all — comparison must degrade to "nothing to compare", not error."""
    result = promote.compare({}, {"trust_model": {"learned_auc": 0.70}})

    assert result.deltas == []
    assert result.clean is True


# --- promote() / rollback() -----------------------------------------------------


def test_promote_swaps_the_candidate_in_and_backs_up_the_old_live_set(tmp_path):
    live_dir = tmp_path / "artifacts"
    candidate_dir = tmp_path / "candidate"
    (live_dir).mkdir()
    (live_dir / "trust_model.joblib").write_bytes(b"old-model-bytes")
    (candidate_dir).mkdir()
    (candidate_dir / "trust_model.joblib").write_bytes(b"new-model-bytes")

    backup_dir = promote.promote(candidate_dir, artifacts_dir=live_dir)

    assert (live_dir / "trust_model.joblib").read_bytes() == b"new-model-bytes"
    assert (backup_dir / "trust_model.joblib").read_bytes() == b"old-model-bytes"
    assert not candidate_dir.exists(), "candidate_dir is cleaned up once its contents have landed"


def test_promote_preserves_a_live_artifact_the_candidate_never_touched(tmp_path):
    """Regression test for exactly the bug live verification (not this test
    suite) caught first: a candidate that only retrained one model has no
    file at all for the others, and an early wholesale-directory-swap
    implementation silently deleted risk_model.joblib from a real, working
    live artifact set because the candidate never produced one. Promotion
    must overlay, not replace.
    """
    live_dir = tmp_path / "artifacts"
    candidate_dir = tmp_path / "candidate"
    live_dir.mkdir()
    (live_dir / "trust_model.joblib").write_bytes(b"old-trust-model")
    (live_dir / "risk_model.joblib").write_bytes(b"untouched-risk-model")
    candidate_dir.mkdir()
    (candidate_dir / "trust_model.joblib").write_bytes(b"new-trust-model")

    promote.promote(candidate_dir, artifacts_dir=live_dir)

    assert (live_dir / "trust_model.joblib").read_bytes() == b"new-trust-model"
    assert (live_dir / "risk_model.joblib").read_bytes() == b"untouched-risk-model"


def test_promote_merges_metrics_json_rather_than_replacing_it(tmp_path):
    """The same preservation property as the artifact file above, applied
    to metrics.json: a trust-only candidate's fresh metrics.json has no
    real_data_risk_model section, and that section must survive promotion
    even though the file itself gets a new trust_model section."""
    live_dir = tmp_path / "artifacts"
    candidate_dir = tmp_path / "candidate"
    _write_metrics(
        live_dir,
        {
            "trust_model": {"learned_auc": 0.65},
            "real_data_risk_model": {"learned_average_precision": 0.77},
        },
    )
    _write_metrics(candidate_dir, {"trust_model": {"learned_auc": 0.70}})

    promote.promote(candidate_dir, artifacts_dir=live_dir)

    merged = json.loads((live_dir / "metrics.json").read_text())
    assert merged["trust_model"]["learned_auc"] == 0.70
    assert merged["real_data_risk_model"]["learned_average_precision"] == 0.77


def test_promote_from_a_fresh_clone_with_no_prior_artifacts(tmp_path):
    """The very first promotion ever — live_dir doesn't exist yet. Must not
    require a backup step that has nothing to back up."""
    live_dir = tmp_path / "artifacts"  # deliberately never created
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    (candidate_dir / "trust_model.joblib").write_bytes(b"first-model-ever")

    promote.promote(candidate_dir, artifacts_dir=live_dir)

    assert (live_dir / "trust_model.joblib").read_bytes() == b"first-model-ever"


def test_rollback_restores_the_previous_artifacts_exactly(tmp_path):
    live_dir = tmp_path / "artifacts"
    candidate_dir = tmp_path / "candidate"
    live_dir.mkdir()
    (live_dir / "trust_model.joblib").write_bytes(b"good-model")
    candidate_dir.mkdir()
    (candidate_dir / "trust_model.joblib").write_bytes(b"bad-model")

    backup_dir = promote.promote(candidate_dir, artifacts_dir=live_dir)
    assert (live_dir / "trust_model.joblib").read_bytes() == b"bad-model"

    promote.rollback(backup_dir, artifacts_dir=live_dir)

    assert (live_dir / "trust_model.joblib").read_bytes() == b"good-model"


# --- main() — the CLI refuses a regression without --force ---------------------


def test_main_refuses_to_promote_a_regressed_candidate_without_force(tmp_path, monkeypatch):
    live_dir = tmp_path / "artifacts"
    candidate_dir = tmp_path / "candidate"
    _write_metrics(live_dir, {"trust_model": {"learned_auc": 0.70}})
    _write_metrics(candidate_dir, {"trust_model": {"learned_auc": 0.40}})

    argv = ["promote.py", str(candidate_dir), "--artifacts-dir", str(live_dir)]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exc_info:
        promote.main()
    assert exc_info.value.code == 1
    # Refused — nothing should have moved.
    assert candidate_dir.exists()
    assert json.loads((live_dir / "metrics.json").read_text())["trust_model"]["learned_auc"] == 0.70


def test_main_promotes_a_regressed_candidate_when_forced_with_a_reason(tmp_path, monkeypatch):
    live_dir = tmp_path / "artifacts"
    candidate_dir = tmp_path / "candidate"
    _write_metrics(live_dir, {"trust_model": {"learned_auc": 0.70}})
    _write_metrics(candidate_dir, {"trust_model": {"learned_auc": 0.40}})

    argv = [
        "promote.py",
        str(candidate_dir),
        "--artifacts-dir",
        str(live_dir),
        "--force",
        "--reason",
        "known short-term regression, accepted for a different reason",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    promote.main()  # must not raise

    assert json.loads((live_dir / "metrics.json").read_text())["trust_model"]["learned_auc"] == 0.40


def test_force_without_a_reason_is_rejected_at_the_argument_level(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["promote.py", "some-dir", "--force"])
    with pytest.raises(SystemExit):
        promote._parse_args()
