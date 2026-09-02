"""Tests for the real-data risk model training pipeline.

Skips when the real dataset hasn't been fetched (`python -m
app.ml.fetch_real_data`) — it's ~150MB, gitignored, and not part of CI's
default flow, same "skip when the dependency isn't there" pattern used
elsewhere in this suite for an unreachable Postgres (see
tests/test_governance.py). Unlike the synthetic-dataset tests in
test_ml_train.py, this doesn't use a small purpose-built config — it
subsamples the one real dataset that exists, keeping every fraud row (only
492 exist in total; discarding any would make the held-out evaluation
meaningless) alongside a modest random sample of the rest, so the test
still exercises genuinely real values rather than a synthetic stand-in.
"""

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import train_test_split

from app.ml.real_data import RISK_MODEL_FEATURES, RealDataSplit, load_real_transactions
from app.ml.train_risk_model import train_risk_model

try:
    _FULL_DF = load_real_transactions()
except Exception:
    _FULL_DF = None


def _small_split(seed: int = 5) -> RealDataSplit:
    fraud = _FULL_DF[_FULL_DF["Class"] == 1]
    legit_sample = _FULL_DF[_FULL_DF["Class"] == 0].sample(n=4000, random_state=seed)
    subset = pd.concat([fraud, legit_sample], ignore_index=True)

    x = subset[RISK_MODEL_FEATURES].to_numpy()
    y = subset["Class"].to_numpy()
    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=0.25, stratify=y, random_state=seed
    )
    return RealDataSplit(
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        n_train_fraud=int(y_train.sum()),
        n_test_fraud=int(y_test.sum()),
    )


@pytest.fixture
def small_split():
    if _FULL_DF is None:
        pytest.skip("real dataset not fetched — run `python -m app.ml.fetch_real_data`")
    return _small_split()


def test_class_labels_are_integers_not_the_quoted_strings_openml_exports(small_split):
    """Regression test for the bug documented in technical-disclosure.md §8:
    OpenML's CSV export wraps Class in literal quotes ('0'/'1'). A
    reader that doesn't strip them produces string labels that scikit-learn
    accepts silently, corrupting every numeric computation downstream."""
    assert small_split.y_train.dtype.kind in "iu"
    assert set(np.unique(small_split.y_train)) <= {0, 1}


def test_risk_model_beats_the_class_frequency_baseline(small_split):
    """The whole point: a model fit to real transaction features should
    discriminate fraud far better than predicting the constant prevalence
    for everything, which is what real_data.RISK_MODEL_FEATURES existing at
    all is supposed to buy over the synthetic-only Simulation Engine."""
    _, metrics = train_risk_model(small_split)

    assert metrics["learned_average_precision"] > metrics["baseline_average_precision"]
    assert metrics["learned_roc_auc"] > metrics["baseline_roc_auc"]
    assert metrics["baseline_roc_auc"] == pytest.approx(0.5, abs=0.05)


def test_risk_score_is_derived_correctly_from_the_trained_model(small_split):
    """RiskModel.predict_risk_score (app/ml/models.py) must agree with the
    raw model probability it wraps — 100 * P(fraud), same direction and
    scale as every other risk_score in this codebase."""
    from app.ml.models import RiskModel

    model, _ = train_risk_model(small_split)
    wrapped = RiskModel(model)

    row = dict(zip(RISK_MODEL_FEATURES, small_split.x_test[0], strict=True))
    expected = 100.0 * model.predict_proba(small_split.x_test[:1])[0, 1]

    assert wrapped.predict_risk_score(row) == pytest.approx(expected, abs=0.01)
