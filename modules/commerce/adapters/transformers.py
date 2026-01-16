"""Data transformation utilities for commerce adapters."""

from __future__ import annotations

from typing import Iterable, List

from modules.commerce.domain import Product, RawProduct, RawOffer


# ============================================================================
# RawOffer -> RawProduct transformations
# ============================================================================


def raw_offer_to_raw_product(offer: RawOffer) -> RawProduct:
    sku = str(offer.variant_attributes.get("sku") or offer.source_id)
    return RawProduct(
        product_id=offer.source_id,
        sku=sku,
        title=offer.title,
        description=offer.description,
        brand=_extract_brand(offer),
        category=str(
            offer.attributes.get("category")
            or offer.variant_attributes.get("category")
            or ""
        ),
        price=offer.price,
        currency=offer.currency,
        availability=offer.availability,
        inventory_quantity=offer.inventory_quantity,
        images=list(offer.media),
        attributes=offer.attributes,
        source_metadata={"source": offer.source},
        source=offer.source,
        merchant_name=offer.merchant_name,
        offer_url=offer.offer_url,
        confidence=offer.confidence,
        completeness=offer.completeness,
    )


def convert_offers(offers: Iterable[RawOffer]) -> List[RawProduct]:
    return [raw_offer_to_raw_product(offer) for offer in offers]


def _extract_brand(offer: RawOffer) -> str:
    if offer.attributes.get("brand_override"):
        return str(offer.attributes["brand_override"])
    if offer.variant_attributes.get("brand"):
        return str(offer.variant_attributes["brand"])
    return str(offer.attributes.get("brand") or "")


# ============================================================================
# RawProduct -> Product normalization
# ============================================================================


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
        capability_embedding=raw.attributes.get("capability_embedding"),
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
