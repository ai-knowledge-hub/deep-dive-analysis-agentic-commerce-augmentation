"""Shared product schemas for the agentic commerce core."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class Product:
    id: str
    name: str
    price: float
    tags: List[str]
    description: str = ""
    empowerment_scores: Dict[str, float] = field(default_factory=dict)
    capabilities_enabled: List[str] = field(default_factory=list)
