"""Seeds the vertical packs: their policies, and agents to govern with them.

A pack's rules are not privileged. They go through `policy_service.create_version`
exactly like anything an operator writes, so they are parsed, validated against
the extended vocabulary, and stored as immutable versions. A rule that shipped
with ATLAS and one authored on a Tuesday afternoon are the same kind of object.

Agents are seeded alongside because a domain field only means something on a
decision that carries it — without an investments agent making investment
decisions, `portfolio_concentration_pct` is a vocabulary entry nobody can
demonstrate.
"""

import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.domains import PACKS
from app.models import Agent, Decision, PolicyCheck, TrustFactor
from app.models.enums import DecisionOutcome, LifecycleState

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

#: One agent per domain capability, with the decisions that exercise its
#: pack's rules. Attributes are the domain values a rule reads — the whole
#: point of the vertical, and absent on every other domain's decisions.
DOMAIN_AGENTS: list[tuple[str, str, str, str, int, list[dict]]] = [
    (
        "agt-funds-01",
        "Fund Allocation Agent",
        "Mutual Funds",
        "Wealth Management",
        88,
        [
            # Clean: inside every limit.
            dict(
                action="Rebalance balanced mandate",
                outcome=DecisionOutcome.APPROVED,
                amount=18_500,
                attributes={
                    "portfolio_concentration_pct": 12.4,
                    "holding_period_days": 420,
                    "security_restricted": "no",
                    "client_risk_profile": "balanced",
                    "suitability_score": 88,
                },
            ),
            # Breaches the concentration cap — blocked by inv-01.
            dict(
                action="Increase position in single equity",
                outcome=DecisionOutcome.BLOCKED,
                amount=94_000,
                attributes={
                    "portfolio_concentration_pct": 31.8,
                    "holding_period_days": 210,
                    "security_restricted": "no",
                    "client_risk_profile": "balanced",
                    "suitability_score": 74,
                },
            ),
            # Unsuitable for a conservative mandate — reviewed by inv-03.
            dict(
                action="Allocate to emerging-markets fund",
                outcome=DecisionOutcome.ESCALATED,
                amount=22_000,
                attributes={
                    "portfolio_concentration_pct": 8.1,
                    "holding_period_days": 95,
                    "security_restricted": "no",
                    "client_risk_profile": "conservative",
                    "suitability_score": 52,
                },
            ),
        ],
    ),
    (
        "agt-travel-safety-01",
        "Traveller Safety Agent",
        "Travel Safety",
        "Global Mobility",
        84,
        [
            dict(
                action="Book flight to Frankfurt",
                outcome=DecisionOutcome.APPROVED,
                amount=1_180,
                attributes={
                    "pii_fields_accessed": 4,
                    "destination_risk_tier": "low",
                    "traveller_consent": "yes",
                    "cross_border_transfer": "yes",
                },
            ),
            # Cross-border transfer without consent — blocked by trv-03.
            dict(
                action="Share itinerary with regional partner",
                outcome=DecisionOutcome.BLOCKED,
                amount=None,
                attributes={
                    "pii_fields_accessed": 6,
                    "destination_risk_tier": "elevated",
                    "traveller_consent": "no",
                    "cross_border_transfer": "yes",
                },
            ),
            # High-risk destination — reviewed by trv-02.
            dict(
                action="Book travel to high-advisory region",
                outcome=DecisionOutcome.ESCALATED,
                amount=3_400,
                attributes={
                    "pii_fields_accessed": 5,
                    "destination_risk_tier": "high",
                    "traveller_consent": "yes",
                    "cross_border_transfer": "no",
                },
            ),
        ],
    ),
    (
        "agt-booking-01",
        "Inventory Booking Agent",
        "Booking",
        "Revenue Management",
        81,
        [
            dict(
                action="Confirm standard reservation",
                outcome=DecisionOutcome.APPROVED,
                amount=640,
                attributes={
                    "inventory_remaining_pct": 42.0,
                    "price_variance_pct": -4.0,
                    "cancellation_window_hours": 48,
                    "overbooking": "no",
                },
            ),
            # Past allocation — blocked by bkg-01.
            dict(
                action="Confirm reservation beyond allocation",
                outcome=DecisionOutcome.BLOCKED,
                amount=890,
                attributes={
                    "inventory_remaining_pct": 0.0,
                    "price_variance_pct": 6.0,
                    "cancellation_window_hours": 24,
                    "overbooking": "yes",
                },
            ),
            # Deep discount — reviewed by bkg-03.
            dict(
                action="Apply retention discount",
                outcome=DecisionOutcome.ESCALATED,
                amount=310,
                attributes={
                    "inventory_remaining_pct": 18.0,
                    "price_variance_pct": -44.0,
                    "cancellation_window_hours": 72,
                    "overbooking": "no",
                },
            ),
        ],
    ),
    (
        "agt-itops-scale-01",
        "Capacity Scaling Agent",
        "Capacity Scaling",
        "Platform Engineering",
        85,
        [
            # Routine, in-window, low-volume — clean.
            dict(
                action="Add two read replicas to reporting database",
                outcome=DecisionOutcome.APPROVED,
                amount=None,
                attributes={
                    "capacity_change_pct": 25.0,
                    "current_utilization_pct": 55.0,
                    "affected_transaction_volume": 45_000,
                    "maintenance_window": "yes",
                },
            ),
            # Mid-day capacity cut outside the change window — blocked by itops-01
            # (and also matches itops-02's volume threshold; block wins either way).
            dict(
                action="Scale down card-authorisation cluster",
                outcome=DecisionOutcome.BLOCKED,
                amount=None,
                attributes={
                    "capacity_change_pct": -15.0,
                    "current_utilization_pct": 40.0,
                    "affected_transaction_volume": 850_000,
                    "maintenance_window": "no",
                },
            ),
            # Large scale-up of a high-volume system, inside the window —
            # still reviewed by itops-02 regardless of direction.
            dict(
                action="Scale up card-authorisation cluster",
                outcome=DecisionOutcome.ESCALATED,
                amount=None,
                attributes={
                    "capacity_change_pct": 60.0,
                    "current_utilization_pct": 88.0,
                    "affected_transaction_volume": 1_200_000,
                    "maintenance_window": "yes",
                },
            ),
        ],
    ),
    (
        "agt-itops-diag-01",
        "System Diagnostics Agent",
        "System Diagnostics",
        "Site Reliability Engineering",
        80,
        [
            # Single-record lookup for a support ticket — clean.
            dict(
                action="Look up customer's recent transaction for support ticket",
                outcome=DecisionOutcome.APPROVED,
                amount=None,
                attributes={"data_sensitivity": "confidential", "query_scope": "single-record"},
            ),
            # Bulk export of regulated data — blocked by itops-03.
            dict(
                action="Export full transaction history for fraud investigation",
                outcome=DecisionOutcome.BLOCKED,
                amount=None,
                attributes={"data_sensitivity": "regulated", "query_scope": "bulk-export"},
            ),
            # Aggregate query over internal-only data — clean.
            dict(
                action="Aggregate query: daily failed-login counts by region",
                outcome=DecisionOutcome.APPROVED,
                amount=None,
                attributes={"data_sensitivity": "internal", "query_scope": "aggregate"},
            ),
        ],
    ),
]


def _factors(rng: random.Random, centre: int) -> list[TrustFactor]:
    return [
        TrustFactor(
            key=key,
            label=FACTOR_LABELS[key],
            score=max(5, min(99, centre + rng.randint(-5, 5))),
            weight=weight,
        )
        for key, weight in FACTOR_WEIGHTS.items()
    ]


def build_domain_agents(
    now: datetime | None = None,
) -> tuple[list[Agent], list[Decision]]:
    """Agents and decisions that exercise each vertical pack's rules."""
    now = now or datetime.now(UTC)
    rng = random.Random(20260824)

    agents: list[Agent] = []
    decisions: list[Decision] = []

    for agent_id, name, capability, owner, trust, actions in DOMAIN_AGENTS:
        agents.append(
            Agent(
                id=agent_id,
                name=name,
                capability=capability,
                owner=owner,
                lifecycle=LifecycleState.HEALTHY if trust >= 82 else LifecycleState.REVIEW,
                trust_score=trust,
                trust_delta=round(rng.uniform(-2, 2), 1),
                decisions_today=len(actions),
                last_active_at=now - timedelta(minutes=rng.randint(5, 240)),
                model=rng.choice(["GPT-4o", "Claude-Sonnet-4"]),
                authority_level=2,
                last_audit_at=(now - timedelta(days=rng.randint(4, 30))).date(),
                last_decision=actions[0]["action"],
                factors=_factors(rng, trust),
            )
        )

        for index, spec in enumerate(actions):
            amount = spec["amount"]
            decisions.append(
                Decision(
                    id=f"{agent_id.upper().replace('AGT-', '')}-{index:03d}",
                    agent_id=agent_id,
                    action=spec["action"],
                    amount_usd=None if amount is None else Decimal(str(amount)),
                    outcome=spec["outcome"],
                    trust_score=trust,
                    risk_score=rng.randint(10, 70),
                    decided_at=now - timedelta(hours=rng.randint(1, 200)),
                    latency_ms=rng.randint(60, 400),
                    rationale=f"Domain seed record for {name}.",
                    # The domain values the pack's rules read. Stored on the
                    # decision's investigation blob so they travel with the
                    # record rather than being recomputed later from state
                    # that has since moved on.
                    investigation={"domainAttributes": spec["attributes"]},
                    policy_checks=[
                        PolicyCheck(
                            policy_id=policy.policy_id,
                            policy_name=policy.name,
                            passed=spec["outcome"] is DecisionOutcome.APPROVED,
                            detail="Seeded domain check",
                        )
                        for pack in PACKS
                        if pack.governs(capability)
                        for policy in pack.policies
                    ],
                )
            )

    return agents, decisions
