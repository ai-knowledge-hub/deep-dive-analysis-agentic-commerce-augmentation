"""Offer-level schema emitted by adapters before product reconstruction."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawOffer:
    source: str  # e.g., shopify, google_shopping
    source_id: str
    merchant_name: Optional[str]
    offer_url: Optional[str]
    title: str
    description: Optional[str]
    price: float
    currency: str
    availability: str
    inventory_quantity: Optional[int]
    variant_attributes: Dict[str, Any] = field(default_factory=dict)
    media: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    completeness: float = 1.0
    inferred_fields: List[str] = field(default_factory=list)


__all__ = ["RawOffer"]
