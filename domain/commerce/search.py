from __future__ import annotations

from typing import Iterable, List, Sequence

from domain.commerce.types import Product


def _matches(product: Product, query: str) -> bool:
    query_lower = query.lower()
    haystack: Sequence[str] = [
        product.name,
        product.description,
        *product.tags,
        *product.capabilities_enabled,
    ]
    return any(query_lower in item.lower() for item in haystack)


def search(
    products: Sequence[Product], query: str, limit: int | None = None
) -> List[Product]:
    if not query:
        results = list(products)
    else:
        results = [product for product in products if _matches(product, query)]
    if limit is not None:
        results = results[:limit]
    return results


def related_by_tag(products: Sequence[Product], tag: str) -> List[Product]:
    return [product for product in products if tag in product.tags]


def list_intent_scores(products: Iterable[Product]) -> List[dict]:
    return [{"id": product.id, "scores": product.intent_scores} for product in products]
