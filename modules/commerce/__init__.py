"""Commerce module - product catalog, search, comparison, and plan building.

This module owns all product-related domain models, services, and adapters.
"""

from __future__ import annotations

from modules.commerce.domain import Product, RawProduct, RawOffer


def search(*args, **kwargs):
    from modules.commerce.search import search as _search

    return _search(*args, **kwargs)


def related_by_tag(*args, **kwargs):
    from modules.commerce.search import related_by_tag as _related_by_tag

    return _related_by_tag(*args, **kwargs)


def list_intent_scores(*args, **kwargs):
    from modules.commerce.search import list_intent_scores as _list_intent_scores

    return _list_intent_scores(*args, **kwargs)


def compare(*args, **kwargs):
    from modules.commerce.compare import compare as _compare

    return _compare(*args, **kwargs)


__all__ = [
    "Product",
    "RawProduct",
    "RawOffer",
    "search",
    "related_by_tag",
    "list_intent_scores",
    "compare",
]
