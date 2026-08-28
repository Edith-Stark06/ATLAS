"""Booking and inventory.

The failure mode here is quiet: an agent that keeps selling past the last unit,
or drifts away from published pricing, does no single dramatic thing. It does
many small ones. So the fields describe pressure on inventory and distance from
the published price rather than the value of one booking.
"""

from app.domains.base import DomainPack, DomainRule
from app.services.policy_engine import FieldSpec

FIELDS = {
    "inventory_remaining_pct": FieldSpec(
        "Inventory Remaining (%)",
        float,
        "Share of allocation still unsold after this booking, 0–100",
    ),
    "price_variance_pct": FieldSpec(
        "Price Variance (%)",
        float,
        "Deviation from the published fare; negative is a discount",
    ),
    "cancellation_window_hours": FieldSpec(
        "Cancellation Window (hours)",
        int,
        "Hours remaining in which the customer could still cancel free",
    ),
    "overbooking": FieldSpec(
        "Overbooking",
        str,
        "Whether this booking exceeds confirmed allocation: yes / no",
    ),
}

BOOKING = DomainPack(
    key="booking",
    label="Booking & Inventory",
    description=(
        "Governs booking agents on inventory pressure and price integrity — "
        "failures that accumulate quietly rather than appearing in one action."
    ),
    capabilities=("Booking", "Inventory Management"),
    fields=FIELDS,
    policies=(
        DomainRule(
            policy_id="bkg-01",
            name="Overbooking Requires Authorisation",
            version="v1.0.0",
            severity="critical",
            scope="Booking agents",
            note=(
                "Selling past confirmed allocation is a commercial decision, not an automatic one."
            ),
            rule={
                "conditions": [{"field": "overbooking", "operator": "eq", "value": "yes"}],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["Booking", "Inventory Management"],
            },
        ),
        DomainRule(
            policy_id="bkg-02",
            name="Last-Units Inventory Guard",
            version="v1.0.0",
            severity="high",
            scope="Booking agents",
            note=(
                "The final few units are where overselling starts. Reviewed near "
                "exhaustion rather than blocked, so the allocation can still be sold."
            ),
            rule={
                "conditions": [{"field": "inventory_remaining_pct", "operator": "lt", "value": 5}],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Booking", "Inventory Management"],
            },
        ),
        DomainRule(
            policy_id="bkg-03",
            name="Deep Discount Review",
            version="v1.0.0",
            severity="high",
            scope="Booking agents",
            note=(
                "Large discounts are the margin leak that never shows up as a "
                "single bad booking. Negative variance is a discount."
            ),
            rule={
                "conditions": [{"field": "price_variance_pct", "operator": "lt", "value": -30}],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Booking", "Inventory Management"],
            },
        ),
    ),
)
