"""Fetches the real-world dataset the risk model (`train_risk_model.py`) is
trained on, and nothing else — no database access, no other artifact.

Run with `python -m app.ml.fetch_real_data`.

## Dataset

"Credit Card Fraud Detection" — 284,807 credit card transactions made by
European cardholders over two days in September 2013, 492 of them (0.172%)
fraudulent. Collected during a research collaboration between Worldline and
the Machine Learning Group of Université Libre de Bruxelles (ULB).

- Source (no account required): OpenML, https://www.openml.org/d/1597
  (direct CSV: https://www.openml.org/data/get_csv/1673544/phpKo8OWT)
- Also distributed via Kaggle (mlg-ulb/creditcardfraud) and Zenodo
  (10.5281/zenodo.7395559) — same underlying data.
- License: Open Database License (ODbL) v1.0 / Database Contents License
  (DbCL) v1.0. Attribution required; the *database* is share-alike if
  redistributed — this project does not redistribute it (see .gitignore),
  only fetches it locally and trains a model on it, so that obligation
  doesn't attach to the trained artifact.
- Citation: Dal Pozzolo, A., Caelen, O., Johnson, R.A., Bontempi, G.
  "Calibrating Probability with Undersampling for Unbalanced Classification."
  IEEE Symposium Series on Computational Intelligence, 2015.

## Why this dataset, and its real limitation

This is genuinely real financial transaction data, not a simulator — 28 of
its 31 columns (`V1`..`V28`) are anonymized via PCA for the cardholders'
privacy, and there is no persistent per-cardholder identity across rows. It
can train a real fraud/risk classifier (train_risk_model.py); it cannot
train ATLAS's Trust Engine, which scores an agent from its *own accumulated
history* — a concept this dataset has no way to represent. See
docs/patent/technical-disclosure.md §5.9 for the full scope statement.
"""

import csv
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"
CSV_PATH = DATA_DIR / "creditcard.csv"
SOURCE_URL = "https://www.openml.org/data/get_csv/1673544/phpKo8OWT"

EXPECTED_COLUMNS = ["Time", *[f"V{i}" for i in range(1, 29)], "Amount", "Class"]
EXPECTED_ROWS = 284_807
EXPECTED_FRAUD_COUNT = 492


def _validate(path: Path) -> None:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = [c.strip('"') for c in next(reader)]
        if header != EXPECTED_COLUMNS:
            raise ValueError(
                f"Unexpected column layout — got {header[:5]}... "
                f"expected {EXPECTED_COLUMNS[:5]}... (mismatched or corrupted download?)"
            )
        n_rows = 0
        n_fraud = 0
        for row in reader:
            n_rows += 1
            # OpenML's CSV export wraps the nominal Class column's values in
            # literal single quotes ('0'/'1'), not bare integers — an ARFF
            # (OpenML's native format) categorical-encoding artifact that
            # leaks into the CSV conversion. Confirmed against the actual
            # downloaded file, not assumed.
            if row[-1].strip("'") == "1":
                n_fraud += 1

    if n_rows != EXPECTED_ROWS or n_fraud != EXPECTED_FRAUD_COUNT:
        raise ValueError(
            f"Row/fraud count mismatch — got {n_rows} rows / {n_fraud} fraud, "
            f"expected {EXPECTED_ROWS} / {EXPECTED_FRAUD_COUNT}. Likely a truncated "
            "or partial download; delete the file and re-run."
        )


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if CSV_PATH.exists():
        print(f"Already present: {CSV_PATH}")
    else:
        print(f"Downloading from {SOURCE_URL} ...")
        try:
            urllib.request.urlretrieve(SOURCE_URL, CSV_PATH)
        except Exception:
            CSV_PATH.unlink(missing_ok=True)
            raise

    print("Validating (row count, fraud count, column layout) ...")
    try:
        _validate(CSV_PATH)
    except ValueError:
        CSV_PATH.unlink(missing_ok=True)
        raise

    print(f"OK — {EXPECTED_ROWS} rows, {EXPECTED_FRAUD_COUNT} labelled fraud, at {CSV_PATH}")
    print("Source: Worldline / ULB Machine Learning Group, ODbL v1.0 — see module docstring.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - CLI entrypoint, report and exit non-zero
        print(f"Failed: {exc}", file=sys.stderr)
        sys.exit(1)
