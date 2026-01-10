"""Commerce domain models - Product, RawProduct, and RawOffer.

These are the canonical representations used throughout the system.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RawOffer:
    """Offer-level schema emitted by adapters before product reconstruction."""

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


@dataclass
class RawProduct:
    """Variant-level record emitted by adapters before enrichment."""

    product_id: str
    sku: str
    title: str
    description: Optional[str]
    brand: str
    category: Optional[str]
    price: float
    currency: str
    availability: str
    inventory_quantity: Optional[int]
    images: List[str] = field(default_factory=list)
    attributes: Dict[str, Any] = field(default_factory=dict)
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    merchant_name: Optional[str] = None
    offer_url: Optional[str] = None
    confidence: float = 1.0
    completeness: float = 1.0


@dataclass
class Product:
    """LLM-ready representation that powers reasoning and empowerment metrics."""

    id: str
    name: str
    price: float
    tags: List[str]
    description: str = ""
    empowerment_scores: Dict[str, float] = field(default_factory=dict)
    capabilities_enabled: List[str] = field(default_factory=list)
    brand: str | None = None
    category: str | None = None
    availability: str = "unknown"
    media: List[str] = field(default_factory=list)
    source: str = "unknown"
    merchant_name: Optional[str] = None
    offer_url: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


__all__ = ["RawOffer", "RawProduct", "Product"]
