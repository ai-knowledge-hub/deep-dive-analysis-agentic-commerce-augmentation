"""Helpers converting RawOffer objects into RawProduct instances."""

from __future__ import annotations

from typing import Iterable, List

from core.schema.offer import RawOffer
from core.schema.product import RawProduct


def raw_offer_to_raw_product(offer: RawOffer) -> RawProduct:
    sku = str(offer.variant_attributes.get("sku") or offer.source_id)
    return RawProduct(
        product_id=offer.source_id,
        sku=sku,
        title=offer.title,
        description=offer.description,
        brand=_extract_brand(offer),
        category=str(offer.attributes.get("category") or offer.variant_attributes.get("category") or ""),
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
