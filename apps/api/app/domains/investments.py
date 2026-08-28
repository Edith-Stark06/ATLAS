"""Mutual funds and portfolio management.

What separates this domain is that the risk is rarely in any single action.
A trade that is fine in isolation can breach a concentration limit, or move a
conservative client's portfolio somewhere it should not go. So the fields here
describe the *position after the action*, not the action alone.
"""

from app.domains.base import DomainPack, DomainRule
from app.services.policy_engine import FieldSpec

FIELDS = {
    "portfolio_concentration_pct": FieldSpec(
        "Portfolio Concentration (%)",
        float,
        "Share of the client's portfolio in one holding *after* this trade, 0–100",
    ),
    "holding_period_days": FieldSpec(
        "Holding Period (days)",
        int,
        "Days the position would have been held at the point of sale",
    ),
    "security_restricted": FieldSpec(
        "Restricted Security",
        str,
        "Whether the instrument is on a restricted or watch list: yes / no",
    ),
    "client_risk_profile": FieldSpec(
        "Client Risk Profile",
        str,
        "Mandated profile: conservative, balanced, aggressive",
    ),
    "suitability_score": FieldSpec(
        "Suitability",
        int,
        "How well the instrument matches the client's mandate, 0–100",
    ),
}

INVESTMENTS = DomainPack(
    key="investments",
    label="Mutual Funds & Portfolio",
    description=(
        "Governs trades and rebalancing where the risk lies in the resulting "
        "position rather than the individual action."
    ),
    capabilities=("Mutual Funds", "Portfolio Management"),
    fields=FIELDS,
    policies=(
        DomainRule(
            policy_id="inv-01",
            name="Single-Holding Concentration Cap",
            version="v1.0.0",
            severity="critical",
            scope="Investment agents",
            note=(
                "Measured after the trade, because a trade that looks small can "
                "still be the one that breaches the limit."
            ),
            rule={
                "conditions": [
                    {"field": "portfolio_concentration_pct", "operator": "gt", "value": 25}
                ],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["Mutual Funds", "Portfolio Management"],
            },
        ),
        DomainRule(
            policy_id="inv-02",
            name="Restricted Security Screen",
            version="v1.0.0",
            severity="critical",
            scope="Investment agents",
            note="No autonomous trading in restricted instruments, at any size.",
            rule={
                "conditions": [{"field": "security_restricted", "operator": "eq", "value": "yes"}],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["Mutual Funds", "Portfolio Management"],
            },
        ),
        DomainRule(
            policy_id="inv-03",
            name="Suitability Floor for Conservative Mandates",
            version="v1.1.0",
            severity="high",
            scope="Investment agents",
            note=(
                "Both conditions must hold: a low suitability score is only a "
                "problem against a mandate that did not ask for it."
            ),
            rule={
                "conditions": [
                    {"field": "client_risk_profile", "operator": "eq", "value": "conservative"},
                    {"field": "suitability_score", "operator": "lt", "value": 70},
                ],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Mutual Funds", "Portfolio Management"],
            },
        ),
        DomainRule(
            policy_id="inv-04",
            name="Short-Holding Redemption Review",
            version="v1.0.0",
            severity="medium",
            scope="Investment agents",
            note=(
                "Short holds often carry an exit fee the client did not expect. "
                "Reviewed rather than blocked — sometimes it is the right call."
            ),
            rule={
                "conditions": [{"field": "holding_period_days", "operator": "lt", "value": 30}],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Mutual Funds", "Portfolio Management"],
            },
        ),
    ),
)
