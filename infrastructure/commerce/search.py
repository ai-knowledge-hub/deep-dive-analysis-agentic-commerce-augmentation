from __future__ import annotations

from typing import Iterable, List, Sequence

from domain.commerce.search import list_intent_scores as _list_intent_scores
from domain.commerce.search import related_by_tag as _related_by_tag
from domain.commerce.search import search as _search
from domain.commerce.types import Product
from infrastructure.commerce.catalog_loader import load_catalog

_CATALOG: list[Product] | None = None


def _get_catalog() -> list[Product]:
    global _CATALOG
    if _CATALOG is None:
        _CATALOG = load_catalog()
    return _CATALOG


def search(
    query: str, limit: int | None = None, *, catalog: Sequence[Product] | None = None
) -> List[Product]:
    return _search(catalog or _get_catalog(), query=query, limit=limit)


def related_by_tag(
    tag: str, *, catalog: Sequence[Product] | None = None
) -> List[Product]:
    return _related_by_tag(catalog or _get_catalog(), tag=tag)


def list_intent_scores(products: Iterable[Product]) -> List[dict]:
    return _list_intent_scores(products)
