"""Unit tests for the synthetic dataset generator — no database, no trained
artifacts required. These guard the properties the whole ML story depends
on: determinism, a non-trivial (not fabricated-perfect) label, and a clean
train/test split that cannot leak an agent's own future into its own past.
"""

import numpy as np

from app.ml.dataset import (
    DatasetConfig,
    build_simulation_training_frame,
    build_trust_training_frame,
    generate_agent_timelines,
    train_test_split_by_agent,
)

SMALL = DatasetConfig(n_agents=24, n_steps=40, seed=1)


def test_generation_is_deterministic():
    a = generate_agent_timelines(SMALL)
    b = generate_agent_timelines(SMALL)
    assert a.equals(b)


def test_different_seeds_produce_different_data():
    a = generate_agent_timelines(SMALL)
    b = generate_agent_timelines(DatasetConfig(n_agents=24, n_steps=40, seed=2))
    assert not a["outcome"].equals(b["outcome"])


def test_row_count_matches_config():
    df = generate_agent_timelines(SMALL)
    assert len(df) == SMALL.n_agents * SMALL.n_steps
    assert df["agent_id"].nunique() == SMALL.n_agents


def test_factor_scores_stay_in_range():
    df = generate_agent_timelines(SMALL)
    for key in ["behavior", "policy", "risk", "context", "history"]:
        col = df[f"factor_{key}"]
        assert col.min() >= 0
        assert col.max() <= 100


def test_outcome_label_is_not_degenerate():
    """All three outcomes must actually occur, and none should dominate to
    the point the label carries no information — either would make the
    baseline-vs-learned comparison meaningless."""
    df = generate_agent_timelines(SMALL)
    freq = df["outcome"].value_counts(normalize=True)
    assert set(freq.index) == {"approved", "escalated", "blocked"}
    assert freq.min() > 0.05


def test_drift_events_are_a_minority_of_steps():
    df = generate_agent_timelines(SMALL)
    assert 0 < df["is_drift_event"].mean() < 0.3


def test_trust_frame_label_is_the_next_decision_not_the_current_one():
    timelines = generate_agent_timelines(SMALL)
    frame = build_trust_training_frame(timelines)

    one_agent = timelines[timelines["agent_id"] == timelines["agent_id"].iloc[0]].sort_values(
        "step"
    )
    one_frame = frame[frame["agent_id"] == one_agent["agent_id"].iloc[0]].sort_values("step")

    # frame drops the last step (no "next" outcome to label it with).
    assert len(one_frame) == len(one_agent) - 1
    for _, row in one_frame.iterrows():
        next_actual = one_agent[one_agent["step"] == row["step"] + 1]["outcome"].iloc[0]
        assert row["label_adverse"] == (next_actual in {"blocked", "escalated"})


def test_simulation_frame_keeps_the_immediate_outcome():
    timelines = generate_agent_timelines(SMALL)
    frame = build_simulation_training_frame(timelines)
    assert len(frame) == len(timelines)
    assert (frame["outcome"] == timelines["outcome"]).all()


def test_split_is_disjoint_and_covers_every_agent():
    timelines = generate_agent_timelines(SMALL)
    train, test = train_test_split_by_agent(timelines, test_fraction=0.25, seed=1)

    train_ids = set(train["agent_id"])
    test_ids = set(test["agent_id"])
    assert train_ids.isdisjoint(test_ids)
    assert train_ids | test_ids == set(timelines["agent_id"])


def test_split_never_puts_one_agents_rows_on_both_sides():
    timelines = generate_agent_timelines(SMALL)
    train, test = train_test_split_by_agent(timelines, seed=3)

    for agent_id in timelines["agent_id"].unique():
        in_train = (train["agent_id"] == agent_id).any()
        in_test = (test["agent_id"] == agent_id).any()
        assert not (in_train and in_test)


def test_split_is_reproducible_for_the_same_seed():
    timelines = generate_agent_timelines(SMALL)
    train_a, _ = train_test_split_by_agent(timelines, seed=5)
    train_b, _ = train_test_split_by_agent(timelines, seed=5)
    assert set(train_a["agent_id"]) == set(train_b["agent_id"])


def test_axis_signal_strength_covers_every_factor():
    """FACTOR_SIGNAL_STRENGTH and FACTOR_AXIS_BLEND must define every factor
    generate_agent_timelines will look up, or generation crashes at runtime
    rather than at import time."""
    from app.ml.dataset import FACTOR_AXIS_BLEND, FACTOR_KEYS, FACTOR_SIGNAL_STRENGTH

    assert set(FACTOR_SIGNAL_STRENGTH) == set(FACTOR_KEYS)
    assert set(FACTOR_AXIS_BLEND) == set(FACTOR_KEYS)
    assert all(0 <= v <= 1 for v in FACTOR_SIGNAL_STRENGTH.values())


def test_true_outcome_weights_sum_to_one():
    """Not a hard requirement of the model, but a sanity check that the
    ground-truth weighting is a proper convex combination — an accidental
    typo here would silently change the outcome-generating process."""
    from app.ml.dataset import TRUE_OUTCOME_WEIGHTS

    assert np.isclose(sum(TRUE_OUTCOME_WEIGHTS.values()), 1.0, atol=0.01)
