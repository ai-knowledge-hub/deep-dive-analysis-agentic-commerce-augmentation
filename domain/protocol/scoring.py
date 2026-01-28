from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from domain.protocol.types import ProtocolCandidate, StructuredQuery


@dataclass(frozen=True)
class StructuredMatch:
    score: float
    matched: List[str]
    missing: List[str]
    notes: List[str]


def score_structured_match(
    query: StructuredQuery, candidate: ProtocolCandidate
) -> StructuredMatch:
    """Pure scoring for protocol candidates.

    This is intentionally simple and deterministic:
    - Hard penalties for missing required attributes
    - Soft penalties for missing commerce fields
    - Budget/availability are treated as constraints when present
    """

    matched: List[str] = []
    missing: List[str] = []
    notes: List[str] = []

    total_points = 0.0
    earned = 0.0

    # Attribute constraints
    for attr in query.required_attributes:
        total_points += 1.0
        if _has_attribute(candidate.attributes, attr):
            earned += 1.0
            matched.append(attr)
        else:
            missing.append(attr)

    # Availability constraint
    if query.require_available_for_sale:
        total_points += 1.0
        available = _is_available(candidate)
        if available:
            earned += 1.0
            matched.append("available_for_sale")
        else:
            missing.append("available_for_sale")
            notes.append("Not available for sale (or availability unknown).")

    # Budget constraint (if supplied)
    if query.price_max is not None:
        total_points += 1.0
        if candidate.price is not None and candidate.price <= query.price_max:
            earned += 1.0
            matched.append("price_max")
        else:
            missing.append("price_max")
            notes.append("Price missing or above budget.")

    # Soft readiness hints (don’t dominate the score)
    soft_fields: List[Tuple[str, Any]] = [
        ("offer_url", candidate.offer_url),
        ("price", candidate.price),
        ("availability", candidate.availability),
    ]
    total_points += 0.5
    earned += 0.5 * (sum(1 for _, v in soft_fields if v) / len(soft_fields))

    score = 0.0 if total_points <= 0 else max(0.0, min(1.0, earned / total_points))
    return StructuredMatch(score=score, matched=matched, missing=missing, notes=notes)


def _has_attribute(attributes: Dict[str, Any], required: str) -> bool:
    key = required.strip().lower()
    if not key:
        return False
    for k, v in attributes.items():
        if str(k).strip().lower() == key:
            if v is None:
                return False
            if isinstance(v, bool):
                return v
            return True
    return False


def _is_available(candidate: ProtocolCandidate) -> bool:
    if candidate.available_for_sale is True:
        return True
    availability = (candidate.availability or "").lower()
    if availability in {"in_stock", "instock", "available", "available_for_sale"}:
        return True
    if candidate.inventory_quantity is not None and candidate.inventory_quantity > 0:
        return True
    return False
