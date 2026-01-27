"""Pure Intentionality profile type."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class IntentionalityProfile:
    """Structured representation of a product in intent-legible terms."""

    product_id: str
    capabilities_enabled: List[str]
    goals_served: List[str] = field(default_factory=list)
    prerequisites: List[str] = field(default_factory=list)
    outcomes_expected: List[str] = field(default_factory=list)
    context_fit: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "capabilities_enabled": list(self.capabilities_enabled),
            "goals_served": list(self.goals_served),
            "prerequisites": list(self.prerequisites),
            "outcomes_expected": list(self.outcomes_expected),
            "context_fit": dict(self.context_fit),
        }


__all__ = ["IntentionalityProfile"]

