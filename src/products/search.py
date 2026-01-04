"""Product search across a mocked catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List, Sequence

from .schemas import Product

CATALOG_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_catalog_empowerment.json"


def _load_catalog(path: Path = CATALOG_PATH) -> List[Product]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return [Product(**item) for item in payload]


CATALOG = _load_catalog()


def _matches(product: Product, query: str) -> bool:
    query_lower = query.lower()
    haystack: Sequence[str] = [product.name, product.description, *product.tags, *product.capabilities_enabled]
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


def list_empowerment_scores(products: Iterable[Product]) -> List[dict]:
    summaries = []
    for product in products:
        summaries.append({"id": product.id, "scores": product.empowerment_scores})
    return summaries
