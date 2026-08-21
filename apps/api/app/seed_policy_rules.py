"""Rule definitions for the seeded policies.

Kept separate from app/seed.py so the rules read as a policy catalogue
rather than being buried in table-construction code. Each entry is the
initial immutable version of that policy's rule.

Every rule here is written against the closed field vocabulary in
app/services/policy_engine.py::EVALUABLE_FIELDS and is validated on insert,
so a typo fails at seed time rather than silently never matching.
"""

#: policy_id -> (rule dict, version label, authoring note)
POLICY_RULES: dict[str, tuple[dict, str, str]] = {
    "pol-01": (
        {
            "conditions": [{"field": "amount_usd", "operator": "gt", "value": 6000}],
            "combinator": "all",
            "effect": "require_human_review",
            "applies_to": ["Travel & Expense"],
        },
        "v2.4.1",
        "Travel bookings above the $6,000 ceiling need a human.",
    ),
    "pol-04": (
        {
            "conditions": [{"field": "amount_usd", "operator": "gt", "value": 2000}],
            "combinator": "all",
            "effect": "require_human_review",
            "applies_to": ["Travel & Expense"],
        },
        "v1.9.0",
        "Entertainment spend cap.",
    ),
    "pol-06": (
        {
            # Applies to every agent: no applies_to restriction.
            "conditions": [{"field": "risk_score", "operator": "gte", "value": 90}],
            "combinator": "all",
            "effect": "block",
            "applies_to": [],
        },
        "v5.0.2",
        "Sanctions screening — extreme risk halts the action outright.",
    ),
    "pol-09": (
        {
            "conditions": [{"field": "amount_usd", "operator": "gt", "value": 1_000_000}],
            "combinator": "all",
            "effect": "block",
            "applies_to": ["Payments"],
        },
        "v3.1.0",
        "Hard cap on a single cross-border settlement batch.",
    ),
    "pol-10": (
        {
            # Either signal alone is enough to warrant a human look.
            "conditions": [
                {"field": "risk_score", "operator": "gt", "value": 70},
                {"field": "amount_usd", "operator": "gt", "value": 500_000},
            ],
            "combinator": "any",
            "effect": "require_human_review",
            "applies_to": ["Payments"],
        },
        "v2.0.4",
        "Liquidity buffer protection: high risk or a very large transfer.",
    ),
    "pol-07": (
        {
            "conditions": [{"field": "amount_usd", "operator": "gt", "value": 500}],
            "combinator": "all",
            "effect": "require_human_review",
            "applies_to": ["Customer Servicing"],
        },
        "v1.4.2",
        "Goodwill credits above $500 need approval.",
    ),
    "pol-13": (
        {
            # Disabled in seed data (Policy.enabled=False) — kept as a
            # realistic example of a drafted-but-not-deployed rule.
            "conditions": [
                {"field": "hour_utc", "operator": "gte", "value": 22},
                {"field": "trust_score", "operator": "lt", "value": 80},
            ],
            "combinator": "all",
            "effect": "require_human_review",
            "applies_to": [],
        },
        "v0.9.0",
        "After-hours autonomy freeze for agents that are not fully trusted.",
    ),
    "pol-14": (
        {
            "conditions": [
                {"field": "trust_score", "operator": "lt", "value": 70},
                {"field": "amount_usd", "operator": "gt", "value": 5000},
            ],
            "combinator": "all",
            "effect": "require_human_review",
            "applies_to": [],
        },
        "v1.0.0",
        "The rule shown in the Policy Brain Builder: low trust plus a large amount.",
    ),
    "pol-15": (
        {
            "conditions": [
                {
                    "field": "agent_lifecycle",
                    "operator": "in",
                    "value": ["anomaly", "review", "onboarding"],
                },
                {"field": "amount_usd", "operator": "gt", "value": 10_000},
            ],
            "combinator": "all",
            "effect": "block",
            "applies_to": [],
        },
        "v1.2.0",
        "Agents not in good standing cannot move large sums unattended.",
    ),
}
