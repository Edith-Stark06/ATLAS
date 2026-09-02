"""Loads and feature-engineers the real fraud dataset fetched by
`fetch_real_data.py`, for `train_risk_model.py`.

Kept separate from `dataset.py` deliberately — that module generates the
*synthetic* data the Trust Engine and Simulation Engine train on, and is
disclosed as such (technical-disclosure.md §5.6). This module wraps a real,
third-party dataset with a different shape and a different set of caveats;
conflating the two in one module would blur exactly the distinction the
patent disclosure needs to state precisely.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

from app.ml.fetch_real_data import CSV_PATH

#: V1..V28 are PCA components of the original (never-published) cardholder
#: features — real signal, but individually meaningless; Amount/Time are the
#: only two columns with a human interpretation. log_amount and hour are
#: engineered from those two, not learned.
PCA_FEATURES = [f"V{i}" for i in range(1, 29)]
RISK_MODEL_FEATURES = ["log_amount", "hour", *PCA_FEATURES]


class RealDataUnavailable(RuntimeError):
    """Raised when creditcard.csv hasn't been fetched yet."""


@dataclass(frozen=True)
class RealDataSplit:
    x_train: np.ndarray
    y_train: np.ndarray
    x_test: np.ndarray
    y_test: np.ndarray
    n_train_fraud: int
    n_test_fraud: int


def load_real_transactions() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise RealDataUnavailable(
            f"{CSV_PATH} not found — run `python -m app.ml.fetch_real_data` first."
        )

    df = pd.read_csv(CSV_PATH)
    # OpenML's CSV export wraps the nominal Class column's values in literal
    # single quotes ('0'/'1'), not bare integers — see fetch_real_data.py's
    # matching note. Confirmed against the actual downloaded file.
    df["Class"] = df["Class"].astype(str).str.strip("'").astype(int)
    df["log_amount"] = np.log1p(df["Amount"])
    # Time is seconds elapsed since the first transaction in the (~2-day)
    # capture window, not a wall-clock timestamp — %86400 recovers hour-of-day
    # under the standard assumption (used throughout the literature on this
    # dataset) that capture started at local midnight.
    df["hour"] = (df["Time"] % 86400) // 3600
    return df


def build_risk_training_split(
    *, test_fraction: float = 0.25, seed: int = 20260902
) -> RealDataSplit:
    """Stratified by Class, not grouped — unlike the synthetic dataset's
    agent-grouped split (dataset.train_test_split_by_agent), there is no
    persistent per-row identity here to group on; every row is an
    independent transaction. Stratification instead guards the one real risk
    in a 0.172%-positive dataset: an unlucky random split could otherwise
    leave the test set with too few (or zero) fraud examples to evaluate
    against at all.
    """
    df = load_real_transactions()
    x = df[RISK_MODEL_FEATURES].to_numpy()
    y = df["Class"].to_numpy()

    x_train, x_test, y_train, y_test = train_test_split(
        x, y, test_size=test_fraction, stratify=y, random_state=seed
    )
    return RealDataSplit(
        x_train=x_train,
        y_train=y_train,
        x_test=x_test,
        y_test=y_test,
        n_train_fraud=int(y_train.sum()),
        n_test_fraud=int(y_test.sum()),
    )
