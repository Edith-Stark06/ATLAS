"""A cohort of agents doing the same job, for comparative benchmarking.

The rest of the seed gives roughly one agent per capability, which is enough
to show governance of a single decision but cannot demonstrate a *ranking* —
there is nobody to rank against. This builds ten agents doing one job, with
the spread of behaviour that makes a comparison say something: a clear
leader, a clear laggard, and several that differ on only one criterion, so
the weighting is visible in the ordering rather than hidden by it.

Deterministic. A fixed seed means the ranking is the same on every run, and
a ranking that reshuffles between runs teaches a reader nothing.
"""

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.models import Agent, Decision, PolicyCheck, TrustFactor, TrustSnapshot
from app.models.enums import DecisionOutcome, LifecycleState

COHORT_CAPABILITY = "Customer Servicing"

#: (suffix, name, profile). Profiles are tuned so agents lose ground on
#: *different* criteria — otherwise the ranking is a single axis wearing five
#: labels and the weighting cannot be seen doing any work.
#:
#: block_rate / escalate_rate / violation_rate are per-decision probabilities;
#: latency_ms is the centre of a right-skewed spread; trust_swing is how far
#: the score wanders, which is what the reliability criterion measures.
COHORT: list[tuple[str, str, dict]] = [
    (
        "cs-01",
        "Tier-1 Resolution Agent",
        dict(
            volume=240,
            block_rate=0.01,
            escalate_rate=0.04,
            violation_rate=0.01,
            latency_ms=90,
            trust=92,
            trust_swing=1,
        ),
    ),
    (
        "cs-02",
        "Billing Enquiry Agent",
        dict(
            volume=210,
            block_rate=0.02,
            escalate_rate=0.06,
            violation_rate=0.02,
            latency_ms=140,
            trust=88,
            trust_swing=2,
        ),
    ),
    (
        "cs-03",
        "Account Recovery Agent",
        dict(
            volume=180,
            block_rate=0.03,
            escalate_rate=0.08,
            violation_rate=0.03,
            latency_ms=210,
            trust=84,
            trust_swing=3,
        ),
    ),
    # Fast but careless. Should rank below slower agents that stay inside the
    # rules — if it does not, the weighting is wrong.
    (
        "cs-04",
        "Rapid Triage Agent",
        dict(
            volume=310,
            block_rate=0.09,
            escalate_rate=0.05,
            violation_rate=0.12,
            latency_ms=60,
            trust=71,
            trust_swing=4,
        ),
    ),
    # Slow but impeccable: the mirror case.
    (
        "cs-05",
        "Complaints Handling Agent",
        dict(
            volume=95,
            block_rate=0.00,
            escalate_rate=0.10,
            violation_rate=0.00,
            latency_ms=1450,
            trust=90,
            trust_swing=2,
        ),
    ),
    (
        "cs-06",
        "Refund Authorisation Agent",
        dict(
            volume=160,
            block_rate=0.04,
            escalate_rate=0.14,
            violation_rate=0.04,
            latency_ms=320,
            trust=79,
            trust_swing=5,
        ),
    ),
    # Decent averages, wild swings. Reliability is the only criterion that
    # catches this one.
    (
        "cs-07",
        "Retention Offers Agent",
        dict(
            volume=145,
            block_rate=0.03,
            escalate_rate=0.09,
            violation_rate=0.05,
            latency_ms=260,
            trust=76,
            trust_swing=18,
        ),
    ),
    (
        "cs-08",
        "Card Replacement Agent",
        dict(
            volume=205,
            block_rate=0.02,
            escalate_rate=0.05,
            violation_rate=0.02,
            latency_ms=175,
            trust=86,
            trust_swing=2,
        ),
    ),
    # Escalates almost everything: safe, barely autonomous, and the most
    # expensive agent in the cohort in human time.
    (
        "cs-09",
        "Dispute Intake Agent",
        dict(
            volume=130,
            block_rate=0.01,
            escalate_rate=0.38,
            violation_rate=0.02,
            latency_ms=230,
            trust=81,
            trust_swing=3,
        ),
    ),
    # Brand new. Should be flagged as thin evidence rather than ranked on a
    # handful of lucky decisions.
    (
        "cs-10",
        "Proactive Outreach Agent",
        dict(
            volume=6,
            block_rate=0.00,
            escalate_rate=0.00,
            violation_rate=0.00,
            latency_ms=120,
            trust=60,
            trust_swing=1,
        ),
    ),
]

FACTOR_LABELS = {
    "behavior": "Behavior Consistency",
    "policy": "Policy Compliance",
    "risk": "Risk Exposure",
    "context": "Context Awareness",
    "history": "Historical Reliability",
}
FACTOR_WEIGHTS = {
    "behavior": 0.22,
    "policy": 0.24,
    "risk": 0.20,
    "context": 0.14,
    "history": 0.20,
}

#: Real policy ids from the seeded set, so these checks aggregate into the
#: hot-spot view alongside everything else rather than forming a private
#: universe the analytics screen cannot see.
CHECKED_POLICIES = [
    ("pol-06", "Sanctions Screening"),
    ("pol-07", "Goodwill Credit Ceiling"),
    ("pol-14", "Low Trust High Value"),
]

HISTORY_POINTS = 8
WINDOW_DAYS = 27

ACTIONS = [
    "Issue goodwill credit",
    "Reverse late fee",
    "Replace lost card",
    "Update billing address",
    "Close dispute case",
]


def _factors(rng: random.Random, centre: int) -> list[TrustFactor]:
    return [
        TrustFactor(
            key=key,
            label=FACTOR_LABELS[key],
            score=max(5, min(99, centre + rng.randint(-6, 6))),
            weight=weight,
        )
        for key, weight in FACTOR_WEIGHTS.items()
    ]


def _lifecycle(trust: int, volume: int) -> LifecycleState:
    if volume < 25:
        return LifecycleState.ONBOARDING
    if trust >= 88:
        return LifecycleState.TRUSTED
    if trust >= 78:
        return LifecycleState.HEALTHY
    return LifecycleState.REVIEW


def build_cohort(
    now: datetime | None = None,
) -> tuple[list[Agent], list[Decision], list[TrustSnapshot]]:
    """Ten agents doing one job, with the activity that makes them comparable."""
    now = now or datetime.now(UTC)
    rng = random.Random(20260823)

    agents: list[Agent] = []
    decisions: list[Decision] = []
    snapshots: list[TrustSnapshot] = []

    for suffix, name, profile in COHORT:
        agent_id = f"agt-{suffix}"
        trust = profile["trust"]

        agents.append(
            Agent(
                id=agent_id,
                name=name,
                capability=COHORT_CAPABILITY,
                owner="Card Member Services",
                lifecycle=_lifecycle(trust, profile["volume"]),
                trust_score=trust,
                trust_delta=round(rng.uniform(-3, 3), 1),
                decisions_today=profile["volume"],
                last_active_at=now - timedelta(minutes=rng.randint(1, 90)),
                model=rng.choice(["GPT-4o", "Claude-Sonnet-4", "ATLAS-Serve-v2"]),
                authority_level=2 if trust >= 85 else 1,
                last_audit_at=(now - timedelta(days=rng.randint(3, 40))).date(),
                last_decision=f"Resolved ticket CS-{rng.randint(1000, 9999)}",
                factors=_factors(rng, trust),
            )
        )

        for index in range(profile["volume"]):
            roll = rng.random()
            if roll < profile["block_rate"]:
                outcome = DecisionOutcome.BLOCKED
            elif roll < profile["block_rate"] + profile["escalate_rate"]:
                outcome = DecisionOutcome.ESCALATED
            else:
                outcome = DecisionOutcome.APPROVED

            # Right-skewed, so p95 sits meaningfully above the median. A
            # symmetric spread would put mean and p95 nearly on top of each
            # other and make the percentile reporting look pointless.
            latency = int(profile["latency_ms"] * rng.choice([0.6, 0.8, 1.0, 1.1, 1.3, 2.4]))

            decisions.append(
                Decision(
                    id=f"CS-{suffix.upper()}-{index:04d}",
                    agent_id=agent_id,
                    action=rng.choice(ACTIONS),
                    amount_usd=Decimal(str(round(rng.uniform(15, 900), 2))),
                    outcome=outcome,
                    trust_score=trust,
                    risk_score=rng.randint(5, 70),
                    decided_at=now
                    - timedelta(days=rng.randint(0, WINDOW_DAYS), minutes=rng.randint(0, 1439)),
                    latency_ms=latency,
                    rationale=f"Cohort seed record for {name}.",
                    policy_checks=[
                        PolicyCheck(
                            policy_id=policy_id,
                            policy_name=policy_name,
                            passed=rng.random() >= profile["violation_rate"],
                            detail="Seeded cohort check",
                        )
                        for policy_id, policy_name in CHECKED_POLICIES
                    ],
                )
            )

        for point in range(HISTORY_POINTS):
            swing = rng.uniform(-profile["trust_swing"], profile["trust_swing"])
            score = max(5, min(99, round(trust + swing)))
            snapshots.append(
                TrustSnapshot(
                    agent_id=agent_id,
                    score=score,
                    base_score=float(score),
                    anomaly_penalty=0.0,
                    factors=[
                        {
                            "key": key,
                            "label": FACTOR_LABELS[key],
                            "score": score,
                            "weight": weight,
                        }
                        for key, weight in FACTOR_WEIGHTS.items()
                    ],
                    reason="seed-cohort",
                    captured_at=now - timedelta(days=(HISTORY_POINTS - point) * 3),
                )
            )

    return agents, decisions, snapshots
