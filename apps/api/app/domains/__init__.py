"""Vertical packs: domain-specific governance vocabulary and rules.

The engine is domain-neutral — trust, risk, amount and lifecycle mean the same
thing everywhere. But a mutual-funds agent needs to be governed on portfolio
concentration, and a travel agent on how much personal data an action touched,
and neither field means anything to the other.

A pack contributes three things: extra fields a rule may reference, the
capabilities it governs, and a set of pre-authored rules. The engine's closed
vocabulary is preserved — it simply becomes core fields *plus* whatever the
registered packs declare, resolved once at import.

Two properties carry the weight here:

- **A domain field is scoped to its domain.** A funds rule cannot be written
  against a travel field, and the authoring UI is told which domain each field
  belongs to so it cannot offer one.
- **An absent domain attribute is unevaluable, not false.** A funds rule
  evaluated against a travel decision finds no `portfolio_concentration_pct`
  and declines to fire, rather than treating the missing value as zero and
  blocking something it knows nothing about.
"""

from app.domains.base import DomainPack
from app.domains.booking import BOOKING
from app.domains.investments import INVESTMENTS
from app.domains.it_ops import IT_OPS
from app.domains.travel import TRAVEL

#: Registered packs, in a deterministic order so the vocabulary endpoint and
#: the authoring UI present the same list on every request.
PACKS: tuple[DomainPack, ...] = (INVESTMENTS, TRAVEL, BOOKING, IT_OPS)


def all_packs() -> tuple[DomainPack, ...]:
    return PACKS


def pack_for_field(field_name: str) -> DomainPack | None:
    """Which pack declares this field, or None for a core field."""
    for pack in PACKS:
        if field_name in pack.fields:
            return pack
    return None


def pack_for_capability(capability: str) -> DomainPack | None:
    """Which pack governs this capability, if any.

    Capabilities not claimed by a pack are governed by the core vocabulary
    alone — which is the correct default, not a gap.
    """
    for pack in PACKS:
        if capability in pack.capabilities:
            return pack
    return None


def domain_fields() -> dict[str, object]:
    """Every field contributed by every pack, keyed by field name.

    Names are asserted unique across packs at import: two packs declaring
    `risk_tier` with different meanings would make a rule's behaviour depend
    on which pack loaded first.
    """
    merged: dict[str, object] = {}
    for pack in PACKS:
        for name, spec in pack.fields.items():
            if name in merged:
                raise ValueError(
                    f"Field '{name}' is declared by more than one domain pack. "
                    "Names must be unique or a rule's meaning depends on load order."
                )
            merged[name] = spec
    return merged


__all__ = [
    "PACKS",
    "BOOKING",
    "INVESTMENTS",
    "IT_OPS",
    "TRAVEL",
    "DomainPack",
    "all_packs",
    "domain_fields",
    "pack_for_capability",
    "pack_for_field",
]
