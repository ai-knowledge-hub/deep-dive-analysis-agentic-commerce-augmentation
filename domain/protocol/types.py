from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

ProtocolType = Literal["acp", "ucp"]


@dataclass(frozen=True)
class StructuredQuery:
    """Structured query constraints for protocol discovery."""

    query_text: str
    price_max: Optional[float] = None
    require_available_for_sale: bool = True
    required_attributes: List[str] = field(default_factory=list)
    merchant_name: Optional[str] = None


@dataclass(frozen=True)
class ProtocolCandidate:
    """Normalized product candidate returned by a protocol adapter."""

    id: str
    name: str
    description: str
    protocol: ProtocolType
    offer_url: Optional[str] = None
    merchant_name: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    availability: Optional[str] = None  # e.g. "in_stock" | "out_of_stock"
    available_for_sale: Optional[bool] = None
    inventory_quantity: Optional[int] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ProtocolReadinessIssue:
    field: str
    severity: Literal["info", "warning", "error"]
    message: str
    fix: Optional[str] = None
