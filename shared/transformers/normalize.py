"""Normalisation helpers that convert raw adapter output into canonical models."""

from __future__ import annotations

from typing import Iterable, List

from modules.commerce.domain import Product, RawProduct


def raw_product_to_product(raw: RawProduct) -> Product:
    return Product(
        id=raw.product_id,
        name=raw.title,
        price=raw.price,
        tags=_derive_tags(raw),
        description=raw.description or "",
        brand=raw.attributes.get("brand_override", raw.brand),
        category=raw.category,
        availability=raw.availability,
        media=raw.images,
        empowerment_scores=_extract_empowerment_scores(raw),
        capabilities_enabled=raw.attributes.get("capabilities", []),
        source=raw.source,
        merchant_name=raw.merchant_name,
        offer_url=raw.offer_url,
        confidence=raw.confidence,
        metadata=raw.source_metadata,
    )


def _derive_tags(raw: RawProduct) -> List[str]:
    tags = list({raw.category or "", *raw.attributes.get("tags", [])})
    return [tag for tag in tags if tag]


def _extract_empowerment_scores(raw: RawProduct) -> dict[str, float]:
    scores = raw.attributes.get("empowerment_scores", {})
    return {key: float(value) for key, value in scores.items()}


def transform_catalog(catalog: Iterable[RawProduct]) -> List[Product]:
    return [raw_product_to_product(item) for item in catalog]
