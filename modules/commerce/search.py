"""Product search across catalogs."""

from __future__ import annotations

import types
from typing import Iterable, List, Sequence

from modules.commerce.adapters import load_catalog
from modules.commerce.domain import Product

CATALOG = load_catalog()


def _matches(product: Product, query: str) -> bool:
    query_lower = query.lower()
    haystack: Sequence[str] = [
        product.name,
        product.description,
        *product.tags,
        *product.capabilities_enabled,
    ]
    return any(query_lower in item.lower() for item in haystack)


def search(query: str, limit: int | None = None) -> List[Product]:
    if not query:
        results = CATALOG
    else:
        results = [product for product in CATALOG if _matches(product, query)]
    if limit is not None:
        results = results[:limit]
    return results


def related_by_tag(tag: str) -> List[Product]:
    return [product for product in CATALOG if tag in product.tags]


def list_intent_scores(products: Iterable[Product]) -> List[dict]:
    summaries = []
    for product in products:
        summaries.append({"id": product.id, "scores": product.intent_scores})
    return summaries


class _CallableModule(types.ModuleType):
    """Allow calling the module to proxy search()."""

    def __call__(self, *args, **kwargs):
        return search(*args, **kwargs)


def _patch_module_callable() -> None:
    import sys

    module = sys.modules.get(__name__)
    if module and not isinstance(module, _CallableModule):
        module.__class__ = _CallableModule


_patch_module_callable()
