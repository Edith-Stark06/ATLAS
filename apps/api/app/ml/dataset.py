"""Synthetic training data for the ML Trust Engine.

There is no real-world decision history to train on — six seeded decisions
teach a model nothing. This module generates a much larger, *labelled*
synthetic dataset with realistic structure: agents following distinct
behavioural archetypes over time, deliberately injected drift events with
known ground truth, and decision outcomes driven by a noisy latent-quality
process rather than a deterministic rule (a model trained on a noiseless
rule would trivially reach 100% accuracy and prove nothing).

This is disclosed as synthetic training methodology, not real operational
data — the point is a reproducible, inspectable data-generating process
that the trained models can be honestly evaluated against.
"""

from dataclasses import dataclass
from enum import StrEnum

import numpy as np
import pandas as pd

FACTOR_KEYS = ["behavior", "policy", "risk", "context", "history"]

#: Per-factor noise scale and bias relative to the shared latent-quality signal.
#: Kept close to 1.0/0.0 so no single factor trivially encodes the label —
#: the model has to combine all five, which is the point of learning weights
#: rather than asserting them.
FACTOR_NOISE = {"behavior": 6.0, "policy": 5.0, "risk": 8.0, "context": 7.0, "history": 5.0}
FACTOR_BIAS = {"behavior": 0.0, "policy": 2.0, "risk": -3.0, "context": 0.0, "history": 1.0}

#: How much each factor reads the "operational" vs "compliance" axis (see
#: _two_axis_trajectories) when it does carry axis signal at all.
FACTOR_AXIS_BLEND = {
    "risk": 0.85,  # mostly operational
    "policy": 0.15,  # mostly compliance
    "behavior": 0.5,
    "context": 0.5,
    "history": 0.5,
}

#: How much of each factor is explained by the two true axes at all, versus
#: idiosyncratic per-step variation unrelated to either. Risk and policy are
#: clean readings of the underlying quality; behaviour/context/history are
#: mostly noise with only a weak connection to it — a realistic case where
#: some collected signals are simply not very diagnostic. This, not the
#: axis blend above, is what makes weight choice matter: a hand-set formula
#: that weights all five comparably is averaging in three largely
#: uninformative signals, diluting the two that actually carry information.
#: A model fit to labelled outcomes can discover which is which; a fixed
#: formula cannot.
FACTOR_SIGNAL_STRENGTH = {
    "risk": 0.88,
    "policy": 0.88,
    "behavior": 0.22,
    "context": 0.18,
    "history": 0.22,
}

#: The *true* relationship between factors and adverse outcomes — deliberately
#: different from BASELINE_WEIGHTS in app.ml.baseline (0.22/0.24/0.20/0.14/0.20).
#: This is the crux of the whole experiment: the baseline is a human guess at
#: factor importance — roughly equal weight to all five. In this synthetic
#: world, outcomes are actually driven almost entirely by two of them; the
#: other three carry only a weak effect. A hand-set formula that treats all
#: five as comparably important is diluting real signal (risk, policy) with
#: near-irrelevant ones — exactly the failure mode a designer cannot see by
#: inspection, and exactly what a model fit to labelled outcomes corrects.
#: If the two weightings matched, no model could out-predict the hand-set
#: formula, and the comparison would prove nothing.
TRUE_OUTCOME_WEIGHTS = {
    "behavior": 0.05,
    "policy": 0.38,
    "risk": 0.45,
    "context": 0.07,
    "history": 0.05,
}


class Archetype(StrEnum):
    """How an agent's latent quality moves over its lifetime."""

    STABLE_HIGH = "stable_high"
    STABLE_MID = "stable_mid"
    DEGRADING = "degrading"
    RECOVERING = "recovering"
    VOLATILE = "volatile"
    ONBOARDING = "onboarding"


#: Roughly matches the mix of behaviours the demo dataset tells a story
#: about (mostly healthy, one degrading, one onboarding).
ARCHETYPE_WEIGHTS = {
    Archetype.STABLE_HIGH: 0.32,
    Archetype.STABLE_MID: 0.24,
    Archetype.DEGRADING: 0.14,
    Archetype.RECOVERING: 0.10,
    Archetype.VOLATILE: 0.10,
    Archetype.ONBOARDING: 0.10,
}


@dataclass(frozen=True)
class DatasetConfig:
    n_agents: int = 320
    n_steps: int = 60
    seed: int = 20260820


def _latent_trajectory(archetype: Archetype, n_steps: int, rng: np.random.Generator) -> np.ndarray:
    """Base latent quality in [0, 1] before drift events or noise."""
    t = np.arange(n_steps)

    if archetype is Archetype.STABLE_HIGH:
        return np.full(n_steps, rng.uniform(0.85, 0.95))
    if archetype is Archetype.STABLE_MID:
        return np.full(n_steps, rng.uniform(0.68, 0.80))
    if archetype is Archetype.DEGRADING:
        start, end = rng.uniform(0.82, 0.92), rng.uniform(0.35, 0.55)
        return start + (end - start) * (t / max(n_steps - 1, 1))
    if archetype is Archetype.RECOVERING:
        start, end = rng.uniform(0.35, 0.5), rng.uniform(0.8, 0.92)
        return start + (end - start) * (t / max(n_steps - 1, 1))
    if archetype is Archetype.VOLATILE:
        base = rng.uniform(0.55, 0.7)
        return base + 0.18 * np.sin(t / rng.uniform(3, 7)) + rng.normal(0, 0.03, n_steps)
    if archetype is Archetype.ONBOARDING:
        # Rises from a low start and levels off — a real "not enough history yet" curve.
        ceiling = rng.uniform(0.6, 0.85)
        return ceiling * (1 - np.exp(-t / rng.uniform(8, 15)))

    raise ValueError(archetype)  # pragma: no cover — exhaustive over the enum


def _two_axis_trajectories(
    archetype: Archetype, n_steps: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """An "operational" and a "compliance" quality axis per agent.

    They are correlated (an agent trending down usually trends down on both)
    but not identical — the compliance axis is the operational one plus a
    slow independent random walk. This is what makes factor choice matter:
    if every factor were a noisy reading of one shared scalar, any
    reasonable set of positive weights would average out to nearly the same
    predictive power (the averaging itself does the work, not the specific
    weights) — which is exactly the failure of the first version of this
    dataset. Two genuinely distinct axes make some factors structurally more
    informative than others, which only a fitted model can discover.

    Returns (operational, compliance, is_drift) — drift is injected on the
    operational axis and inherited by compliance, since a systemic issue
    plausibly shows up on both.
    """
    operational = _latent_trajectory(archetype, n_steps, rng)
    operational, is_drift = _inject_drift_events(
        operational, rng, allow=archetype != Archetype.ONBOARDING
    )

    walk = np.cumsum(rng.normal(0, 0.09, n_steps))
    walk -= walk.mean()
    compliance = np.clip(operational + walk, 0.02, 0.98)

    return operational, compliance, is_drift


def _inject_drift_events(
    latent: np.ndarray, rng: np.random.Generator, *, allow: bool
) -> tuple[np.ndarray, np.ndarray]:
    """Superimpose 0–2 sustained level-shift events with known ground truth.

    Returns (latent_with_drift, is_drift_step). Drift events are what the
    anomaly detector is evaluated against — without an injected, labelled
    event there is no ground truth to measure precision/recall on.
    """
    n = len(latent)
    is_drift = np.zeros(n, dtype=bool)
    if not allow or n < 12:
        return latent, is_drift

    latent = latent.copy()
    n_events = rng.choice([0, 1, 2], p=[0.45, 0.4, 0.15])

    for _ in range(int(n_events)):
        duration = rng.integers(4, 9)
        start = rng.integers(5, max(n - duration - 1, 6))
        magnitude = rng.uniform(0.15, 0.35) * rng.choice([-1, 1], p=[0.75, 0.25])
        end = min(start + duration, n)
        latent[start:end] = np.clip(latent[start:end] + magnitude, 0.02, 0.98)
        is_drift[start:end] = True

    return latent, is_drift


def _decision_outcome(
    operational: float, factors: dict[str, float], rng: np.random.Generator
) -> tuple[str, float, float, float, int]:
    """Sample one decision's outcome and its auxiliary features.

    Outcome depends on the *realized, noisy* factor scores through
    TRUE_OUTCOME_WEIGHTS — not on either latent axis directly, and not on
    BASELINE_WEIGHTS. A hand-set formula using the wrong weights
    systematically mis-ranks decisions; a model fit to labelled outcomes has
    to recover the true weighting to predict well. That gap is what the
    baseline-vs-learned comparison in train.py measures.

    Probability is a noisy sigmoid, not a hard threshold — a threshold rule
    would let a model memorise it perfectly and the resulting AUC would be
    meaningless.
    """
    risk_score = float(np.clip(100 * (1 - operational) + rng.normal(0, 9), 0, 100))
    amount = float(np.exp(rng.normal(7.5, 1.6)))  # log-normal, a few $ to ~$2M
    hour = int(rng.integers(0, 24))
    policy_pass_rate = float(np.clip(factors["policy"] / 100 + rng.normal(0, 0.05), 0, 1))

    true_signal = sum(TRUE_OUTCOME_WEIGHTS[k] * factors[k] / 100 for k in FACTOR_KEYS)

    logit = 6.0 * (true_signal - 0.62)
    logit -= 0.35 * (amount > 50_000)
    logit -= 0.5 * (hour < 5 or hour > 22)
    logit += rng.normal(0, 0.5)
    p_compliant = 1 / (1 + np.exp(-logit))

    roll = rng.uniform(0, 1)
    if roll < p_compliant:
        outcome = "approved"
    elif roll < p_compliant + (1 - p_compliant) * 0.6:
        outcome = "escalated"
    else:
        outcome = "blocked"

    return outcome, risk_score, amount, policy_pass_rate, hour


def generate_agent_timelines(config: DatasetConfig | None = None) -> pd.DataFrame:
    """One row per (agent, time step): factor scores, ground-truth drift flag,
    and the decision sampled at that step.

    agent_id is train/test split boundary — an agent's whole timeline stays
    on one side of the split, or the model would leak information about an
    agent from its own future into its own past.
    """
    config = config or DatasetConfig()
    rng = np.random.default_rng(config.seed)

    archetypes = list(ARCHETYPE_WEIGHTS.keys())
    weights = list(ARCHETYPE_WEIGHTS.values())

    rows: list[dict] = []
    for agent_idx in range(config.n_agents):
        # Indexing avoids numpy coercing the Archetype enum list into a
        # fixed-width string array (and silently truncating the values).
        archetype = archetypes[rng.choice(len(archetypes), p=weights)]
        operational, compliance, is_drift = _two_axis_trajectories(archetype, config.n_steps, rng)
        authority_level = int(rng.integers(1, 5))

        for step in range(config.n_steps):
            op = float(np.clip(operational[step], 0.01, 0.99))
            comp = float(np.clip(compliance[step], 0.01, 0.99))
            factors = {}
            for key in FACTOR_KEYS:
                axis_reading = FACTOR_AXIS_BLEND[key] * op + (1 - FACTOR_AXIS_BLEND[key]) * comp
                # i.i.d. per (agent, step, factor) — deliberately uncorrelated
                # with the true axes and with the other factors, so it cannot
                # substitute for real signal the way a merely noisier copy of
                # the same axis could.
                idiosyncratic = rng.uniform(0.0, 1.0)
                strength = FACTOR_SIGNAL_STRENGTH[key]
                blended = strength * axis_reading + (1 - strength) * idiosyncratic
                factors[key] = float(
                    np.clip(
                        blended * 100 + FACTOR_BIAS[key] + rng.normal(0, FACTOR_NOISE[key]),
                        0,
                        100,
                    )
                )
            outcome, risk_score, amount, policy_pass_rate, hour = _decision_outcome(
                op, factors, rng
            )

            rows.append(
                {
                    "agent_id": f"synth-{agent_idx:04d}",
                    "archetype": archetype.value,
                    "step": step,
                    "authority_level": authority_level,
                    "latent_quality": (op + comp) / 2,
                    "is_drift_event": bool(is_drift[step]),
                    "outcome": outcome,
                    "risk_score": risk_score,
                    "amount_usd": amount,
                    "policy_pass_rate": policy_pass_rate,
                    "hour": hour,
                    **{f"factor_{k}": v for k, v in factors.items()},
                }
            )

    return pd.DataFrame(rows)


def build_trust_training_frame(timelines: pd.DataFrame) -> pd.DataFrame:
    """Features = factor scores at step t. Label = was the *next* decision
    for this agent adverse (blocked or escalated)?

    This is a forward-looking label deliberately: the trust score should
    predict near-term risk, not describe the decision that already happened.
    """
    df = timelines.sort_values(["agent_id", "step"]).copy()
    df["next_outcome"] = df.groupby("agent_id")["outcome"].shift(-1)
    df["label_adverse"] = df["next_outcome"].isin(["blocked", "escalated"]).astype(int)
    # The last step per agent has no "next" decision — drop it.
    df = df.dropna(subset=["next_outcome"]).reset_index(drop=True)
    return df


def build_simulation_training_frame(timelines: pd.DataFrame) -> pd.DataFrame:
    """Features describing a decision at the moment it is made, label = its
    actual outcome. This is what the Simulation Engine's outcome classifier
    trains on.
    """
    df = timelines.copy()
    df["trust_proxy"] = df[[f"factor_{k}" for k in FACTOR_KEYS]].mean(axis=1)
    return df


def train_test_split_by_agent(
    df: pd.DataFrame, *, test_fraction: float = 0.25, seed: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split by agent_id, never by row — a row-level split would leak an
    agent's own future into its own training data."""
    # np.array(..., dtype=object): pandas' unique() returns a pandas
    # StringArray, which numpy's shuffle refuses to guarantee correctness on.
    agent_ids = np.array(df["agent_id"].unique(), dtype=object)
    rng = np.random.default_rng(seed)
    rng.shuffle(agent_ids)

    n_test = max(1, int(len(agent_ids) * test_fraction))
    test_ids = set(agent_ids[:n_test])

    is_test = df["agent_id"].isin(test_ids)
    return df.loc[~is_test].reset_index(drop=True), df.loc[is_test].reset_index(drop=True)
