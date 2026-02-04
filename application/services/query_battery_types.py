from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class GeneratedQuery:
    query_text: str
    query_type: str
    intent_archetype: Optional[str] = None
    constraints: Optional[Dict[str, Any]] = None
    weight: float = 1.0


__all__ = ["GeneratedQuery"]
