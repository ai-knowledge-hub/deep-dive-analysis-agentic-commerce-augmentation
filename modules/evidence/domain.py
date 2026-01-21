"""Domain models for evidence-first product representations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class EvidenceProduct:
    """Product-like representation extracted from open-web evidence."""

    id: str
    name: str
    description: str
    source: str
    url: Optional[str] = None
    price: Optional[float] = None
    confidence: float = 0.3
    raw_text: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ["EvidenceProduct"]
