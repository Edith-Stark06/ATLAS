"""Travel — safety and privacy.

The money in a travel booking is rarely the exposure. What matters is whose
personal data the action touched and where it is sending a person. Both are
things a purely financial rule set cannot see, which is why they are fields
rather than an amount threshold.
"""

from app.domains.base import DomainPack, DomainRule
from app.services.policy_engine import FieldSpec

FIELDS = {
    "pii_fields_accessed": FieldSpec(
        "PII Fields Accessed",
        int,
        "Count of distinct personal data fields the action read, e.g. passport, DOB",
    ),
    "destination_risk_tier": FieldSpec(
        "Destination Risk Tier",
        str,
        "Advisory level for the destination: low, elevated, high, prohibited",
    ),
    "traveller_consent": FieldSpec(
        "Traveller Consent",
        str,
        "Whether the traveller consented to this data use: yes / no",
    ),
    "cross_border_transfer": FieldSpec(
        "Cross-Border Data Transfer",
        str,
        "Whether personal data would leave its origin jurisdiction: yes / no",
    ),
}

TRAVEL = DomainPack(
    key="travel",
    label="Travel — Safety & Privacy",
    description=(
        "Governs travel actions on who they expose and where they send someone, "
        "rather than on what they cost."
    ),
    capabilities=("Travel & Expense", "Travel Safety"),
    fields=FIELDS,
    policies=(
        DomainRule(
            policy_id="trv-01",
            name="Prohibited Destination Block",
            version="v1.0.0",
            severity="critical",
            scope="Travel agents",
            note="No autonomous booking into a prohibited advisory tier, at any price.",
            rule={
                "conditions": [
                    {"field": "destination_risk_tier", "operator": "eq", "value": "prohibited"}
                ],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["Travel & Expense", "Travel Safety"],
            },
        ),
        DomainRule(
            policy_id="trv-02",
            name="High-Risk Destination Review",
            version="v1.0.0",
            severity="high",
            scope="Travel agents",
            note=(
                "A person is going there. Reviewed rather than blocked, because "
                "sometimes the trip is necessary and someone should own that call."
            ),
            rule={
                "conditions": [
                    {"field": "destination_risk_tier", "operator": "eq", "value": "high"}
                ],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Travel & Expense", "Travel Safety"],
            },
        ),
        DomainRule(
            policy_id="trv-03",
            name="Consent Required for Cross-Border Transfer",
            version="v1.0.0",
            severity="critical",
            scope="Travel agents",
            note=(
                "Moving personal data across a border without consent is a "
                "regulatory breach regardless of how routine the booking is."
            ),
            rule={
                "conditions": [
                    {"field": "cross_border_transfer", "operator": "eq", "value": "yes"},
                    {"field": "traveller_consent", "operator": "eq", "value": "no"},
                ],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["Travel & Expense", "Travel Safety"],
            },
        ),
        DomainRule(
            policy_id="trv-04",
            name="Bulk PII Access Review",
            version="v1.0.0",
            severity="medium",
            scope="Travel agents",
            note=(
                "An action reading an unusual number of personal fields is worth "
                "a look even when each field is individually justified."
            ),
            rule={
                "conditions": [{"field": "pii_fields_accessed", "operator": "gt", "value": 8}],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Travel & Expense", "Travel Safety"],
            },
        ),
    ),
)
