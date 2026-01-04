"""MCP tool wrapper for product search."""

from __future__ import annotations

from src.products import search as product_search


def run(query: str) -> dict:
    results = product_search.search(query)
    payload = [
        {
            "id": product.id,
            "name": product.name,
            "price": product.price,
            "confidence": product.confidence,
            "source": product.source,
            "merchant_name": product.merchant_name,
            "offer_url": product.offer_url,
            "capabilities_enabled": product.capabilities_enabled,
            "tags": product.tags,
        }
        for product in results
    ]
    return {"results": payload}
