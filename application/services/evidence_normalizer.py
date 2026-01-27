"""Application-layer normalization for evidence representations."""

from __future__ import annotations

import re
from typing import List

from domain.evidence.types import EvidenceProduct
from modules.commerce.domain import Product


def to_product(evidence: EvidenceProduct) -> Product:
    return Product(
        id=evidence.id,
        name=evidence.name,
        price=evidence.price or 0.0,
        tags=_tags_from_text(evidence.description or evidence.name),
        description=evidence.description or evidence.raw_text or "",
        source=evidence.source,
        offer_url=evidence.url,
        confidence=float(evidence.confidence or 0.3),
        metadata={"evidence": True, "url": evidence.url},
    )


def _tags_from_text(text: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]{4,}", (text or "").lower())
    return sorted(set(tokens))[:6]


__all__ = ["to_product"]

