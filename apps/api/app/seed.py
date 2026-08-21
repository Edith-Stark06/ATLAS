"""Seed the database with the reference governance dataset.

Run with `python -m app.seed` (add `--reset` to wipe first). Idempotent:
re-running replaces the seeded rows rather than duplicating them.

This is the same dataset the console rendered from fixtures in Phase 1, so the
UI is directly comparable before and after the switch to live data.
"""

import argparse
import asyncio
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, update

from app.core import security
from app.core.compat import configure_event_loop
from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.ml import models as ml_models
from app.models import (
    ActivityItem,
    ActivityTone,
    Agent,
    Decision,
    DecisionOutcome,
    LedgerEntry,
    LifecycleState,
    Policy,
    PolicyCheck,
    PolicyVersion,
    Role,
    Severity,
    SimulationOutcome,
    SimulationRun,
    TrustFactor,
    TrustSnapshot,
    User,
)
from app.seed_policy_rules import POLICY_RULES
from app.services import auth_service, policy_engine, trust_service


def _dt(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC)


FACTOR_LABELS = {
    "behavior": "Behavior Consistency",
    "policy": "Policy Compliance",
    "risk": "Risk Exposure",
    "context": "Context Awareness",
    "history": "Historical Reliability",
}
FACTOR_WEIGHTS = {"behavior": 0.22, "policy": 0.24, "risk": 0.20, "context": 0.14, "history": 0.20}


def _factors(**scores: int) -> list[TrustFactor]:
    return [
        TrustFactor(key=key, label=FACTOR_LABELS[key], score=score, weight=FACTOR_WEIGHTS[key])
        for key, score in scores.items()
    ]


def build_agents() -> list[Agent]:
    return [
        Agent(
            id="agt-travel-01",
            name="Travel Booking Agent",
            capability="Travel & Expense",
            owner="Corporate Services",
            lifecycle=LifecycleState.TRUSTED,
            trust_score=94,
            trust_delta=1.2,
            decisions_today=4820,
            last_active_at=_dt("2026-08-19T14:52:10Z"),
            model="GPT-4-Turbo",
            authority_level=2,
            last_audit_at=date(2026, 8, 12),
            last_decision="Approved booking TRX-992A",
            factors=_factors(behavior=96, policy=99, risk=90, context=92, history=95),
        ),
        Agent(
            id="agt-expense-02",
            name="Expense Approval Agent",
            capability="Travel & Expense",
            owner="Finance Operations",
            lifecycle=LifecycleState.REVIEW,
            trust_score=72,
            trust_delta=-6.4,
            decisions_today=1930,
            last_active_at=_dt("2026-08-19T14:49:38Z"),
            model="Claude-Sonnet-4",
            authority_level=2,
            last_audit_at=date(2026, 7, 30),
            last_decision="Escalated reimbursement TRX-9917",
            factors=_factors(behavior=68, policy=81, risk=64, context=75, history=73),
        ),
        Agent(
            id="agt-dispute-03",
            name="Dispute Resolution Agent",
            capability="Customer Servicing",
            owner="Card Member Services",
            lifecycle=LifecycleState.ANOMALY,
            trust_score=87,
            trust_delta=-4.1,
            decisions_today=2610,
            last_active_at=_dt("2026-08-19T14:46:02Z"),
            model="GPT-4o",
            authority_level=3,
            last_audit_at=date(2026, 8, 5),
            last_decision="Issued goodwill credit TRX-9902",
            factors=_factors(behavior=82, policy=94, risk=85, context=88, history=89),
        ),
        Agent(
            id="agt-fraud-04",
            name="Fraud Detection Agent",
            capability="Risk & Fraud",
            owner="Global Risk",
            lifecycle=LifecycleState.TRUSTED,
            trust_score=97,
            trust_delta=0.4,
            decisions_today=12470,
            last_active_at=_dt("2026-08-19T14:53:01Z"),
            model="ATLAS-Risk-v3",
            authority_level=4,
            last_audit_at=date(2026, 8, 18),
            last_decision="Froze card TRX-9871",
            factors=_factors(behavior=98, policy=99, risk=95, context=96, history=97),
        ),
        Agent(
            id="agt-payment-05",
            name="Payment Orchestration Agent",
            capability="Payments",
            owner="Payments Platform",
            lifecycle=LifecycleState.HEALTHY,
            trust_score=89,
            trust_delta=2.0,
            decisions_today=8340,
            last_active_at=_dt("2026-08-19T14:51:22Z"),
            model="Claude-Opus-4",
            authority_level=3,
            last_audit_at=date(2026, 8, 9),
            last_decision="Blocked settlement TRX-9884",
            factors=_factors(behavior=90, policy=93, risk=84, context=87, history=90),
        ),
        Agent(
            id="agt-onboard-06",
            name="Merchant Onboarding Agent",
            capability="Merchant Services",
            owner="Merchant Platform",
            lifecycle=LifecycleState.ONBOARDING,
            trust_score=58,
            trust_delta=5.8,
            decisions_today=210,
            last_active_at=_dt("2026-08-19T14:30:07Z"),
            model="Llama-4-70B",
            authority_level=1,
            last_audit_at=date(2026, 8, 16),
            last_decision="Deferred KYC review MRC-221",
            factors=_factors(behavior=55, policy=70, risk=48, context=60, history=52),
        ),
    ]


def build_policies() -> list[Policy]:
    rows = [
        (
            "pol-01",
            "Travel Spend Ceiling",
            "v2.4.1",
            "Travel & Expense agents",
            True,
            Severity.HIGH,
            "2026-08-19T14:41:55Z",
            48200,
            12,
        ),
        (
            "pol-04",
            "Entertainment Spend Limit",
            "v1.9.0",
            "Expense agents",
            True,
            Severity.MEDIUM,
            "2026-08-17T09:12:00Z",
            19300,
            61,
        ),
        (
            "pol-06",
            "Sanctions Screening",
            "v5.0.2",
            "All agents",
            True,
            Severity.CRITICAL,
            "2026-08-12T16:04:30Z",
            241000,
            0,
        ),
        (
            "pol-09",
            "Cross-Border Settlement Cap",
            "v3.1.0",
            "Payment agents",
            True,
            Severity.CRITICAL,
            "2026-08-15T11:22:10Z",
            8340,
            3,
        ),
        (
            "pol-10",
            "Liquidity Buffer",
            "v2.0.4",
            "Payment agents",
            True,
            Severity.HIGH,
            "2026-08-18T08:47:19Z",
            8340,
            7,
        ),
        (
            "pol-07",
            "Goodwill Credit Ceiling",
            "v1.4.2",
            "Servicing agents",
            True,
            Severity.LOW,
            "2026-08-10T13:55:41Z",
            26100,
            18,
        ),
        (
            "pol-13",
            "After-Hours Autonomy Freeze",
            "v0.9.0",
            "All agents",
            False,
            Severity.MEDIUM,
            "2026-08-05T18:20:00Z",
            0,
            0,
        ),
        (
            "pol-14",
            "Low Trust High Value",
            "v1.0.0",
            "All agents",
            True,
            Severity.HIGH,
            "2026-08-19T10:05:00Z",
            52400,
            34,
        ),
        (
            "pol-15",
            "Unproven Agent Spend Limit",
            "v1.2.0",
            "All agents",
            True,
            Severity.CRITICAL,
            "2026-08-16T07:30:00Z",
            52400,
            9,
        ),
    ]
    return [
        Policy(
            id=pid,
            name=name,
            version=version,
            scope=scope,
            enabled=enabled,
            severity=severity,
            updated_at=_dt(updated),
            evaluations_24h=evals,
            violations_24h=viol,
        )
        for pid, name, version, scope, enabled, severity, updated, evals, viol in rows
    ]


def build_decisions() -> list[Decision]:
    return [
        Decision(
            id="EXP-8892-BL",
            agent_id="agt-expense-02",
            action="Approve reimbursement — TechSolutions Inc",
            amount_usd=Decimal("12450.00"),
            outcome=DecisionOutcome.BLOCKED,
            trust_score=71,
            risk_score=84,
            decided_at=_dt("2026-08-19T07:14:22Z"),
            latency_ms=214,
            rationale=(
                "Blocked pending human review. Three compounding risk factors crossed the "
                "autonomous execution threshold simultaneously, and the agent's trust score "
                "had already fallen 23 points in the preceding 24 hours."
            ),
            investigation={
                "summary": (
                    "The transaction requested by the Expense Approval Agent for $12,450.00 to "
                    "vendor 'TechSolutions Inc' was blocked due to multiple compounding risk "
                    "factors crossing the autonomous execution threshold."
                ),
                "criticalFactors": [
                    {
                        "key": "threshold",
                        "title": "Spending Threshold Anomaly",
                        "detail": (
                            "Vendor 'TechSolutions Inc' has a historical average transaction size "
                            "of $2,100. This request exceeds the 3-sigma standard deviation for "
                            "the vendor category."
                        ),
                        "severity": "critical",
                    },
                    {
                        "key": "timing",
                        "title": "Behavioural Timing",
                        "detail": (
                            "Request originated at 03:14 EST, outside normal operating hours for "
                            "the initiating department."
                        ),
                        "severity": "high",
                    },
                ],
                "actionRequired": (
                    "A human operator with Level 2 clearance must review the vendor history and "
                    "confirm the legitimacy of this off-hours, high-value request."
                ),
                "trustBefore": 94,
                "confidence": 98,
                "riskVector": {"financial": 90, "fraud": 85, "operational": 35, "regulatory": 20},
                "merchant": "TechSolutions Inc",
                "requestedAtLocal": "03:14 EST",
                "trace": [
                    {"key": "request", "label": "Ingestion", "status": "done"},
                    {"key": "policy", "label": "Validation", "status": "done"},
                    {"key": "trust", "label": "Model Eval", "status": "done"},
                    {
                        "key": "simulation",
                        "label": "Risk Assessment",
                        "status": "failed",
                        "detail": "Block triggered",
                    },
                    {"key": "ledger", "label": "Gov Ledger", "status": "done"},
                ],
            },
            policy_checks=[
                PolicyCheck(
                    policy_id="pol-04",
                    policy_name="Entertainment Spend Limit",
                    passed=False,
                    detail="$12,450 exceeds $2,000 cap",
                ),
                PolicyCheck(
                    policy_id="pol-14",
                    policy_name="Vendor Transaction Variance",
                    passed=False,
                    detail="5.9× the vendor's historical average",
                ),
                PolicyCheck(
                    policy_id="pol-15",
                    policy_name="Operating-Hours Window",
                    passed=False,
                    detail="Originated 03:14 EST",
                ),
                PolicyCheck(policy_id="pol-06", policy_name="Sanctions Screening", passed=True),
            ],
        ),
        Decision(
            id="TRX-992A",
            agent_id="agt-travel-01",
            action="Book flight LHR → JFK, business class",
            amount_usd=Decimal("4820.00"),
            outcome=DecisionOutcome.APPROVED,
            trust_score=94,
            risk_score=12,
            decided_at=_dt("2026-08-19T14:52:10Z"),
            latency_ms=284,
            rationale=(
                "Approved. The agent's trust score (94) exceeds the 85 threshold for travel "
                "bookings above $2,500. All applicable policies passed, and simulation projected "
                "a 96% probability of a compliant, low-impact outcome."
            ),
            policy_checks=[
                PolicyCheck(
                    policy_id="pol-01",
                    policy_name="Travel Spend Ceiling",
                    passed=True,
                    detail="$4,820 under $6,000 cap",
                ),
                PolicyCheck(policy_id="pol-02", policy_name="Preferred Carrier", passed=True),
                PolicyCheck(
                    policy_id="pol-03",
                    policy_name="Advance Booking Window",
                    passed=True,
                    detail="21 days ahead",
                ),
                PolicyCheck(policy_id="pol-06", policy_name="Sanctions Screening", passed=True),
            ],
        ),
        Decision(
            id="TRX-9917",
            agent_id="agt-expense-02",
            action="Approve reimbursement — client dinner, 14 attendees",
            amount_usd=Decimal("3180.00"),
            outcome=DecisionOutcome.ESCALATED,
            trust_score=72,
            risk_score=61,
            decided_at=_dt("2026-08-19T14:49:38Z"),
            latency_ms=412,
            rationale=(
                "Escalated to human review. The agent's trust score fell to 72 after six policy "
                "exceptions in the last 24 hours — below the 80 threshold required for autonomous "
                "approval at this amount."
            ),
            policy_checks=[
                PolicyCheck(
                    policy_id="pol-04",
                    policy_name="Entertainment Spend Limit",
                    passed=False,
                    detail="$3,180 exceeds $2,000 cap",
                ),
                PolicyCheck(policy_id="pol-05", policy_name="Receipt Completeness", passed=True),
                PolicyCheck(policy_id="pol-06", policy_name="Sanctions Screening", passed=True),
            ],
        ),
        Decision(
            id="TRX-9902",
            agent_id="agt-dispute-03",
            action="Issue goodwill credit — disputed charge",
            amount_usd=Decimal("240.00"),
            outcome=DecisionOutcome.APPROVED,
            trust_score=87,
            risk_score=24,
            decided_at=_dt("2026-08-19T14:46:02Z"),
            latency_ms=198,
            rationale=(
                "Approved. Credit amount is well within the goodwill ceiling and the card member "
                "has no repeat-claim history."
            ),
            policy_checks=[
                PolicyCheck(
                    policy_id="pol-07",
                    policy_name="Goodwill Credit Ceiling",
                    passed=True,
                    detail="$240 under $500 cap",
                ),
                PolicyCheck(policy_id="pol-08", policy_name="Repeat Claimant Check", passed=True),
            ],
        ),
        Decision(
            id="TRX-9884",
            agent_id="agt-payment-05",
            action="Route settlement batch — EU corridor",
            amount_usd=Decimal("1284000.00"),
            outcome=DecisionOutcome.BLOCKED,
            trust_score=89,
            risk_score=88,
            decided_at=_dt("2026-08-19T14:38:19Z"),
            latency_ms=631,
            rationale=(
                "Blocked before execution. Simulation projected a 71% probability of "
                "breaching the intraday liquidity buffer. Recommended action: split into "
                "three batches under $500K."
            ),
            investigation={
                "summary": (
                    "A $1.28M single-batch EU settlement was blocked because it exceeds the "
                    "cross-border cap and would drive the intraday liquidity buffer to 3.2%."
                ),
                "criticalFactors": [
                    {
                        "key": "cap",
                        "title": "Cross-Border Settlement Cap",
                        "detail": (
                            "$1.28M exceeds the $1M hard cap for a single cross-border batch."
                        ),
                        "severity": "critical",
                    },
                    {
                        "key": "liquidity",
                        "title": "Liquidity Buffer Erosion",
                        "detail": "Projected buffer of 3.2% falls below the 5% regulatory floor.",
                        "severity": "high",
                    },
                ],
                "actionRequired": "Split the batch into three transfers under $500K and re-submit.",
                "trustBefore": 89,
                "confidence": 97,
                "riskVector": {"financial": 92, "fraud": 15, "operational": 61, "regulatory": 78},
                "trace": [
                    {"key": "request", "label": "Ingestion", "status": "done"},
                    {
                        "key": "policy",
                        "label": "Validation",
                        "status": "failed",
                        "detail": "2 caps breached",
                    },
                    {"key": "trust", "label": "Model Eval", "status": "done"},
                    {
                        "key": "simulation",
                        "label": "Risk Assessment",
                        "status": "failed",
                        "detail": "Block triggered",
                    },
                    {"key": "ledger", "label": "Gov Ledger", "status": "done"},
                ],
            },
            policy_checks=[
                PolicyCheck(
                    policy_id="pol-09",
                    policy_name="Cross-Border Settlement Cap",
                    passed=False,
                    detail="$1.28M exceeds $1M single-batch cap",
                ),
                PolicyCheck(policy_id="pol-06", policy_name="Sanctions Screening", passed=True),
                PolicyCheck(
                    policy_id="pol-10",
                    policy_name="Liquidity Buffer",
                    passed=False,
                    detail="Buffer would fall to 3.2%",
                ),
            ],
        ),
        Decision(
            id="TRX-9871",
            agent_id="agt-fraud-04",
            action="Freeze card — suspected account takeover",
            amount_usd=None,
            outcome=DecisionOutcome.APPROVED,
            trust_score=97,
            risk_score=8,
            decided_at=_dt("2026-08-19T14:31:47Z"),
            latency_ms=94,
            rationale=(
                "Approved. Highest-trust agent in the estate (97) acting within its designated "
                "authority. Device fingerprint and geo-velocity signals both indicate account "
                "takeover with high confidence."
            ),
            policy_checks=[
                PolicyCheck(policy_id="pol-11", policy_name="Freeze Authorization", passed=True),
                PolicyCheck(
                    policy_id="pol-12", policy_name="Card Member Notification", passed=True
                ),
            ],
        ),
    ]


def build_simulations() -> list[SimulationRun]:
    return [
        SimulationRun(
            id="sim-4472",
            decision_id="EXP-8892-BL",
            scenario="Auto-approve $12,450 reimbursement to TechSolutions Inc at 03:14 EST",
            agent_name="Expense Approval Agent",
            amount_usd=Decimal("12450.00"),
            trust_score=71,
            confidence=99.2,
            recommendation=DecisionOutcome.ESCALATED,
            ran_at=_dt("2026-08-19T07:14:22Z"),
            duration_ms=214,
            request=[
                {"label": "Agent", "value": "Expense Approval Agent"},
                {"label": "Department", "value": "Finance Operations"},
                {"label": "Action", "value": "Approve Reimbursement"},
                {"label": "Amount", "value": "$12,450.00"},
                {"label": "Merchant", "value": "TechSolutions Inc"},
                {"label": "Time", "value": "03:14 EST"},
                {"label": "Current Trust", "value": "71 / 100"},
                {"label": "Policy Active", "value": "v2.4.1"},
            ],
            outcomes=[
                SimulationOutcome(
                    label="Approve",
                    probability=0.18,
                    financial_impact_usd=Decimal("-12450.00"),
                    risk_score=84,
                    compliant=False,
                    customer_experience="High",
                    compliance_risk="Medium",
                ),
                SimulationOutcome(
                    label="Human Review",
                    probability=0.64,
                    financial_impact_usd=Decimal("-12450.00"),
                    risk_score=22,
                    compliant=True,
                    customer_experience="Good",
                    compliance_risk="Safe",
                    recommended=True,
                ),
                SimulationOutcome(
                    label="Block",
                    probability=0.18,
                    financial_impact_usd=Decimal("0.00"),
                    risk_score=31,
                    compliant=True,
                    customer_experience="Poor",
                    compliance_risk="Safe",
                ),
            ],
        ),
        SimulationRun(
            id="sim-4471",
            decision_id="TRX-9884",
            scenario="Route $1.28M EU settlement batch as a single transfer",
            agent_name="Payment Orchestration Agent",
            amount_usd=Decimal("1284000.00"),
            trust_score=89,
            confidence=97.4,
            recommendation=DecisionOutcome.BLOCKED,
            ran_at=_dt("2026-08-19T14:38:19Z"),
            duration_ms=631,
            request=[
                {"label": "Agent", "value": "Payment Orchestration Agent"},
                {"label": "Department", "value": "Payments Platform"},
                {"label": "Action", "value": "Route Settlement Batch"},
                {"label": "Amount", "value": "$1,284,000.00"},
                {"label": "Corridor", "value": "EU"},
                {"label": "Current Trust", "value": "89 / 100"},
            ],
            outcomes=[
                SimulationOutcome(
                    label="Settles cleanly",
                    probability=0.29,
                    financial_impact_usd=Decimal("0.00"),
                    risk_score=22,
                    compliant=True,
                    customer_experience="Good",
                    compliance_risk="Safe",
                ),
                SimulationOutcome(
                    label="Breaches liquidity buffer",
                    probability=0.71,
                    financial_impact_usd=Decimal("-184000.00"),
                    risk_score=88,
                    compliant=False,
                    customer_experience="Poor",
                    compliance_risk="High",
                ),
                SimulationOutcome(
                    label="Split into three batches",
                    probability=0.92,
                    financial_impact_usd=Decimal("-2400.00"),
                    risk_score=18,
                    compliant=True,
                    customer_experience="Good",
                    compliance_risk="Safe",
                    recommended=True,
                ),
            ],
        ),
        SimulationRun(
            id="sim-4470",
            decision_id="TRX-992A",
            scenario="Book business-class LHR to JFK at $4,820",
            agent_name="Travel Booking Agent",
            amount_usd=Decimal("4820.00"),
            trust_score=94,
            confidence=99.6,
            recommendation=DecisionOutcome.APPROVED,
            ran_at=_dt("2026-08-19T14:52:10Z"),
            duration_ms=284,
            request=[
                {"label": "Agent", "value": "Travel Booking Agent"},
                {"label": "Department", "value": "Corporate Services"},
                {"label": "Action", "value": "Book Flight"},
                {"label": "Amount", "value": "$4,820.00"},
                {"label": "Route", "value": "LHR to JFK"},
                {"label": "Current Trust", "value": "94 / 100"},
            ],
            outcomes=[
                SimulationOutcome(
                    label="Compliant booking",
                    probability=0.96,
                    financial_impact_usd=Decimal("-4820.00"),
                    risk_score=12,
                    compliant=True,
                    customer_experience="High",
                    compliance_risk="Safe",
                    recommended=True,
                ),
                SimulationOutcome(
                    label="Fare change breaches cap",
                    probability=0.04,
                    financial_impact_usd=Decimal("-6400.00"),
                    risk_score=58,
                    compliant=False,
                    customer_experience="Good",
                    compliance_risk="Medium",
                ),
            ],
        ),
    ]


def build_activity() -> list[ActivityItem]:
    rows = [
        (
            "a1",
            "Travel Agent approved booking TRX-992A.",
            "2026-08-19T14:52:10Z",
            ActivityTone.SUCCESS,
        ),
        (
            "a2",
            "Expense Agent routed for human review.",
            "2026-08-19T14:49:38Z",
            ActivityTone.WARNING,
        ),
        (
            "a3",
            "Trust Score updated for Dispute Agent (91 → 87).",
            "2026-08-19T14:46:02Z",
            ActivityTone.INFO,
        ),
        (
            "a4",
            "Policy version v2.4.1 deployed to production.",
            "2026-08-19T14:41:55Z",
            ActivityTone.INFO,
        ),
        (
            "a5",
            "Simulation predicted compliance violation — blocked.",
            "2026-08-19T14:38:19Z",
            ActivityTone.DANGER,
        ),
        (
            "a6",
            "Governance Ledger synchronized (18,402 entries).",
            "2026-08-19T14:35:44Z",
            ActivityTone.INFO,
        ),
    ]
    return [ActivityItem(id=i, message=m, at=_dt(t), tone=tone) for i, m, t, tone in rows]


#: Historical rounds to backfill, and the spacing between them.
HISTORY_ROUNDS = 8
HISTORY_INTERVAL = timedelta(hours=6)

#: Where each agent's trust started, HISTORY_ROUNDS ago. Chosen so the seeded
#: story is coherent: the Expense agent visibly deteriorates, the Merchant
#: Onboarding agent climbs, and the rest hold steady.
HISTORY_ORIGIN = {
    "agt-travel-01": 91,
    "agt-expense-02": 94,
    "agt-dispute-03": 92,
    "agt-fraud-04": 96,
    "agt-payment-05": 86,
    "agt-onboard-06": 44,
}


def build_trust_history(
    agents: list[Agent], *, now: datetime, trust_model=None
) -> list[TrustSnapshot]:
    """Backfill synthetic trust history for the demo dataset.

    This is fabricated *seed* data, which is the point of a seed script — it
    gives drift detection and forecasting something to work on out of the box.
    Nothing at runtime invents history: the API only ever reads what is stored.

    When a trained model is available (`trust_model`, from
    app.ml.models.load_trust_model), history is scored *with it* — the whole
    backfilled series is ML-native, not just the newest point. Without this,
    seeding before training would leave old heuristic-scored history sitting
    under a live ML-scored present, and every agent would show as sharply
    "drifting" the moment a model is trained — an artifact of the transition,
    not real behaviour. Falls back to interpolating the scalar score directly
    when no model is on disk yet.

    The walk is deterministic (linear interpolation plus a fixed wobble) so
    repeated seeding produces identical history.
    """
    snapshots: list[TrustSnapshot] = []

    for agent in agents:
        origin_score = HISTORY_ORIGIN.get(agent.id, agent.trust_score)
        current_factors = {f.key: f.score for f in agent.factors}
        current_mean = sum(current_factors.values()) / len(current_factors)
        # Scale every factor by the same ratio so the backfill's overall level
        # matches HISTORY_ORIGIN while preserving each factor's relative shape.
        ratio = origin_score / current_mean if current_mean else 1.0
        origin_factors = {k: max(0.0, min(100.0, v * ratio)) for k, v in current_factors.items()}

        # Rounds are written oldest → newest, ending one interval before now so
        # the live recompute that follows becomes the most recent point.
        for step in range(HISTORY_ROUNDS):
            progress = step / (HISTORY_ROUNDS - 1)
            wobble_sign = 1 if step % 2 else -1
            interp_factors = {
                key: max(
                    0.0,
                    min(
                        100.0,
                        origin_factors[key]
                        + (current_factors[key] - origin_factors[key]) * progress
                        + wobble_sign * (step % 3) * 0.6,
                    ),
                )
                for key in current_factors
            }

            base_score = sum(interp_factors[f.key] * f.weight for f in agent.factors) / sum(
                f.weight for f in agent.factors
            )

            if trust_model is not None:
                score = int(round(trust_model.predict(interp_factors).score))
            else:
                score = int(round(base_score))

            captured = now - HISTORY_INTERVAL * (HISTORY_ROUNDS - step)
            snapshots.append(
                TrustSnapshot(
                    agent_id=agent.id,
                    score=score,
                    base_score=round(base_score, 2),
                    anomaly_penalty=0.0,
                    factors=[
                        {
                            "key": f.key,
                            "label": f.label,
                            "score": interp_factors[f.key],
                            "weight": f.weight,
                        }
                        for f in agent.factors
                    ],
                    reason="seed",
                    captured_at=captured,
                )
            )

    return snapshots


async def ensure_bootstrap_admin(session) -> str:
    """Create the first admin account, if and only if no users exist.

    A fresh deployment has to be reachable by someone, and the alternative to
    a bootstrap account is a chicken-and-egg problem where creating the first
    admin requires being an admin.

    Guarded on the whole table rather than on this one email: once any account
    exists, an operator has taken ownership, and silently re-creating a known
    default admin underneath them would be a backdoor. `Settings` separately
    refuses to start outside development while the password is still the
    documented default.
    """
    settings = get_settings()

    if await auth_service.count_users(session) > 0:
        return "users already exist — bootstrap admin not created"

    session.add(
        User(
            email=settings.bootstrap_admin_email.strip().lower(),
            name="ATLAS Administrator",
            password_hash=security.hash_password(settings.bootstrap_admin_password),
            role=Role.ADMIN,
        )
    )
    await session.commit()
    return f"bootstrap admin created: {settings.bootstrap_admin_email}"


async def seed(reset: bool = False) -> None:
    now = datetime.now(UTC)

    async with AsyncSessionLocal() as session:
        if reset:
            # Order matters: children before parents.
            # policies.active_version_id points at policy_versions, and
            # policy_versions.policy_id points back — clear the pointer first
            # or neither table can be deleted.
            await session.execute(update(Policy).values(active_version_id=None))
            for model in (
                SimulationOutcome,
                SimulationRun,
                PolicyCheck,
                Decision,
                TrustSnapshot,
                TrustFactor,
                Agent,
                PolicyVersion,
                Policy,
                ActivityItem,
                # The ledger is append-only in the application, but --reset is
                # a development wipe of the governance dataset, not a business
                # operation. Leaving it would keep a chain whose entries
                # reference decisions that no longer exist.
                LedgerEntry,
                # Users and API keys are deliberately NOT reset. They are
                # credentials, not governance data, and silently deleting a
                # colleague's admin account on a shared dev database to reload
                # sample agents is a surprise nobody wants.
            ):
                await session.execute(delete(model))
            await session.commit()

        agents = build_agents()
        policies = build_policies()
        session.add_all(agents)
        session.add_all(policies)
        await session.flush()  # agents must exist before decisions reference them

        # Give each policy its initial immutable rule version and activate it.
        for policy in policies:
            entry = POLICY_RULES.get(policy.id)
            if entry is None:
                continue
            rule, version, note = entry
            policy_engine.parse_rule(rule)  # fail loudly at seed time on a typo
            policy_version = PolicyVersion(
                policy_id=policy.id,
                version=version,
                rule=rule,
                note=note,
                created_by="seed",
                created_at=now,
            )
            session.add(policy_version)
            await session.flush()
            policy.active_version_id = policy_version.id
            policy.version = version

        session.add_all(build_decisions())
        await session.flush()  # decisions must exist before simulations reference them

        session.add_all(build_simulations())
        session.add_all(build_activity())
        trust_model = ml_models.load_trust_model()
        session.add_all(build_trust_history(agents, now=now, trust_model=trust_model))

        await session.commit()

        # The authoritative current score is whatever the Trust Engine computes
        # from the seeded factors and decisions — not the hand-written value.
        evaluated = await trust_service.recompute_all(session, reason="seed-recompute", now=now)

        bootstrap_note = await ensure_bootstrap_admin(session)

    print(
        "Seeded: 6 agents, 9 policies (with rule versions), 6 decisions, "
        "3 simulations, 6 activity items, "
        f"{len(agents) * HISTORY_ROUNDS} trust snapshots"
    )
    for agent, evaluation in evaluated:
        drift = " (drift)" if evaluation.drift.detected else ""
        print(f"  {agent.id:<18} {evaluation.score:>3}  {evaluation.lifecycle.value}{drift}")
    print(f"  {bootstrap_note}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed the ATLAS database")
    parser.add_argument("--reset", action="store_true", help="delete existing rows first")
    args = parser.parse_args()

    configure_event_loop()
    asyncio.run(seed(reset=args.reset))


if __name__ == "__main__":
    main()
