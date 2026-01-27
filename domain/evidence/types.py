"""Pure domain types for evidence-first flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EvidenceProduct:
    id: str
    name: str
    description: str
    source: str = "web"
    url: Optional[str] = None
    price: Optional[float] = None
    confidence: float = 0.3
    raw_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ["EvidenceProduct"]

