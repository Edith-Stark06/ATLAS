"""IT operations: infrastructure scaling and system/log diagnostics.

The one mentor-feedback direction never addressed — a genuinely new action
domain rather than an extension of the financial one. Two distinct jobs
share this pack rather than each getting its own, mirroring how booking.py
governs two related capabilities (Booking, Inventory Management) off one
field/rule set split by concern:

- Capacity Scaling: changing how much infrastructure a system has, where
  the failure mode is an unplanned change to something carrying real
  transaction volume — the banking-specific blast radius, not a dollar
  amount (most of these actions have none).
- System Diagnostics: querying or exporting production data for
  troubleshooting, where the failure mode is a export whose sensitivity or
  scope exceeds what an autonomous agent should be trusted to move
  unsupervised.

"Absent stays absent" (PolicyContext.attributes) does the separation
between the two automatically: a scaling decision's attributes never
populate data_sensitivity/query_scope, so the diagnostics rules simply
find nothing to evaluate against it, and vice versa — no cross-capability
interference to design around.
"""

from app.domains.base import DomainPack, DomainRule
from app.services.policy_engine import FieldSpec

FIELDS = {
    "capacity_change_pct": FieldSpec(
        "Capacity Change (%)",
        float,
        "Signed change to provisioned capacity; negative is a reduction",
    ),
    "current_utilization_pct": FieldSpec(
        "Current Utilization (%)",
        float,
        "Resource utilization at the moment the change was requested, 0–100",
    ),
    "affected_transaction_volume": FieldSpec(
        "Affected Transaction Volume",
        int,
        "Daily transactions flowing through the system being scaled",
    ),
    "maintenance_window": FieldSpec(
        "Maintenance Window",
        str,
        "Whether this change falls inside an approved change window: yes / no",
    ),
    "data_sensitivity": FieldSpec(
        "Data Sensitivity",
        str,
        "Classification of the data touched: public / internal / confidential / regulated",
    ),
    "query_scope": FieldSpec(
        "Query Scope",
        str,
        "Breadth of the query or export: single-record / aggregate / bulk-export",
    ),
}

IT_OPS = DomainPack(
    key="it_ops",
    label="IT Operations",
    description=(
        "Governs system analysis, log analysis, and application/transaction "
        "capacity scaling in banking infrastructure — actions with no natural "
        "dollar amount, but with real production blast radius and data-"
        "sensitivity risk of their own."
    ),
    capabilities=("Capacity Scaling", "System Diagnostics"),
    fields=FIELDS,
    policies=(
        DomainRule(
            policy_id="itops-01",
            name="Capacity Reduction Outside Maintenance Window",
            version="v1.0.0",
            severity="critical",
            scope="Capacity scaling agents",
            note=(
                "An unplanned mid-day capacity cut to a live system is one of the "
                "most common real causes of production incidents — the window, not "
                "the size of the cut, is what makes it planned."
            ),
            rule={
                "conditions": [
                    {"field": "maintenance_window", "operator": "eq", "value": "no"},
                    {"field": "capacity_change_pct", "operator": "lt", "value": -10},
                ],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["Capacity Scaling"],
            },
        ),
        DomainRule(
            policy_id="itops-02",
            name="High-Volume System Scaling Requires Review",
            version="v1.0.0",
            severity="high",
            scope="Capacity scaling agents",
            note=(
                "Any change — either direction — to a system carrying this much "
                "transaction volume gets a human, the same way booking.py reviews "
                "near-exhausted inventory rather than blocking it outright."
            ),
            rule={
                "conditions": [
                    {
                        "field": "affected_transaction_volume",
                        "operator": "gt",
                        "value": 500_000,
                    }
                ],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["Capacity Scaling"],
            },
        ),
        DomainRule(
            policy_id="itops-03",
            name="Bulk Export of Regulated Data",
            version="v1.0.0",
            severity="critical",
            scope="System diagnostics agents",
            note=(
                "A bulk export of regulated data by an autonomous agent, without "
                "explicit sign-off, is exactly the kind of action this system "
                "exists to gate before it happens rather than audit after."
            ),
            rule={
                "conditions": [
                    {"field": "data_sensitivity", "operator": "eq", "value": "regulated"},
                    {"field": "query_scope", "operator": "eq", "value": "bulk-export"},
                ],
                "combinator": "all",
                "effect": "block",
                "applies_to": ["System Diagnostics"],
            },
        ),
        DomainRule(
            policy_id="itops-04",
            name="Confidential Bulk Export Requires Review",
            version="v1.0.0",
            severity="high",
            scope="System diagnostics agents",
            note="One step below regulated data — still flagged, not silently allowed.",
            rule={
                "conditions": [
                    {"field": "data_sensitivity", "operator": "eq", "value": "confidential"},
                    {"field": "query_scope", "operator": "eq", "value": "bulk-export"},
                ],
                "combinator": "all",
                "effect": "require_human_review",
                "applies_to": ["System Diagnostics"],
            },
        ),
    ),
)
