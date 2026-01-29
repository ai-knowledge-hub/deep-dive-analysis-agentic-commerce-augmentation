from __future__ import annotations

from typing import Any, Dict, List

from domain.commerce.search import search as search_products
from domain.commerce.types import Product


def product_from_record(record: Dict[str, Any]) -> Product:
    metadata = record.get("metadata") or {}
    price = metadata.get("price")
    try:
        price_value = float(price) if price is not None else 0.0
    except (TypeError, ValueError):
        price_value = 0.0

    confidence = metadata.get("confidence")
    try:
        confidence_value = float(confidence) if confidence is not None else 0.7
    except (TypeError, ValueError):
        confidence_value = 0.7

    capabilities = (
        metadata.get("capabilities_enabled") or metadata.get("capabilities") or []
    )
    tags = metadata.get("tags") or []

    return Product(
        id=str(record.get("id") or ""),
        name=str(record.get("name") or ""),
        description=str(record.get("description") or ""),
        price=price_value,
        tags=list(tags),
        capabilities_enabled=list(capabilities),
        intentionality_profile=metadata.get("intentionality_profile"),
        source=str(metadata.get("source") or "product"),
        merchant_name=metadata.get("merchant_name"),
        offer_url=metadata.get("offer_url") or metadata.get("url"),
        confidence=confidence_value,
        metadata=metadata,
    )


def search_products_for_client(
    *,
    deps: Any,
    query: str,
    client_id: str,
    brand_id: str | None = None,
    limit: int = 10,
) -> List[Product]:
    if brand_id:
        rows = deps.clients.list_products(brand_id=brand_id)
        products = [product_from_record(row) for row in rows]
        return search_products(products, query=query, limit=limit)

    rows = deps.clients.search_products_for_client(
        client_id=client_id, query=query, limit=limit
    )
    return [product_from_record(row) for row in rows]


__all__ = ["product_from_record", "search_products_for_client"]
