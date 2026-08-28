"""What a vertical pack is."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DomainRule:
    """A pre-authored rule shipped with a pack.

    Carried as a plain dict rather than a parsed `Rule` so packs stay free of
    a circular import with the engine, and so the same structure can be
    seeded, versioned and re-validated by the ordinary policy path. A pack's
    rules are not privileged — they go through the same parser as anything an
    operator writes.
    """

    policy_id: str
    name: str
    version: str
    severity: str
    scope: str
    rule: dict[str, Any]
    note: str = ""


@dataclass(frozen=True)
class DomainPack:
    key: str
    label: str
    description: str
    #: Agent capabilities this pack governs. A capability claimed by no pack
    #: is governed by the core vocabulary alone, which is the right default
    #: rather than a gap.
    capabilities: tuple[str, ...]
    #: Extra fields a rule may reference within this domain, keyed by name.
    #: Values are `policy_engine.FieldSpec`; typed as Any to keep packs
    #: importable without the engine.
    fields: dict[str, Any] = field(default_factory=dict)
    policies: tuple[DomainRule, ...] = ()

    def governs(self, capability: str) -> bool:
        return capability in self.capabilities
