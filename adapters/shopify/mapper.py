"""Map Shopify products into canonical offers and raw variants."""

from __future__ import annotations

from typing import Dict, Iterable, Iterator, List

from core.schema.offer import RawOffer
from core.schema.product import RawProduct
from core.transformers.offers import raw_offer_to_raw_product
from core.utils.text import strip_html

from .metafields import derive_capabilities, extract_llm_metafields


def shopify_product_to_offers(product: Dict) -> List[RawOffer]:
    description = strip_html(product.get("body_html"))
    images = [image.get("src", "") for image in product.get("images", []) if image.get("src")]
    metafields = extract_llm_metafields(product)
    offers: List[RawOffer] = []
    for variant in product.get("variants", []):
        attributes = {
            **metafields,
            "capabilities": derive_capabilities(metafields),
            "tags": [tag.strip() for tag in product.get("tags", "").split(",") if tag.strip()],
            "empowerment_scores": _collect_empowerment_scores(metafields),
        }
        variant_attributes = {
            "sku": variant.get("sku"),
            "option1": variant.get("option1"),
            "option2": variant.get("option2"),
            "option3": variant.get("option3"),
            "brand": product.get("vendor"),
        }
        offers.append(
            RawOffer(
                source="shopify",
                source_id=str(variant.get("id") or product["id"]),
                merchant_name=product.get("vendor"),
                offer_url=None,
                title=product.get("title", "Unnamed Product"),
                description=description,
                price=float(variant.get("price", 0) or 0),
                currency=_variant_currency(variant),
                availability=_availability_from_variant(variant),
                inventory_quantity=variant.get("inventory_quantity"),
                variant_attributes=variant_attributes,
                media=images,
                attributes=attributes,
                confidence=1.0,
                completeness=1.0,
                inferred_fields=[],
            )
        )
    return offers


def iter_offers(products: Iterable[Dict]) -> Iterator[RawOffer]:
    for product in products:
        yield from shopify_product_to_offers(product)


def iter_raw_products(products: Iterable[Dict]) -> Iterator[RawProduct]:
    for offer in iter_offers(products):
        yield raw_offer_to_raw_product(offer)


def _variant_currency(variant: Dict) -> str:
    presentment = variant.get("presentment_prices") or []
    if presentment:
        price_payload = presentment[0].get("price") or {}
        code = price_payload.get("currency_code")
        if code:
            return code
    return variant.get("currency") or "USD"


def _availability_from_variant(variant: Dict) -> str:
    quantity = variant.get("inventory_quantity")
    if quantity is None:
        return "unknown"
    return "in_stock" if quantity > 0 else "out_of_stock"


def _collect_empowerment_scores(attrs: Dict[str, str]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for key, value in attrs.items():
        if not key.endswith("_score"):
            continue
        try:
            scores[key] = float(value)
        except (TypeError, ValueError):
            continue
    return scores
