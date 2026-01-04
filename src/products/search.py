"""Product search across a mocked catalog."""

from __future__ import annotations

from typing import List

from .schemas import Product

CATALOG = [
    Product(id="desk-01", name="Ergo Desk", price=599, tags=["workspace", "ergonomic"]),
    Product(id="chair-05", name="Lumbar Chair", price=349, tags=["workspace", "health"]),
    Product(id="lamp-02", name="Focus Lamp", price=129, tags=["lighting", "focus"]),
]


def search(query: str) -> List[Product]:
    query_lower = query.lower()
    return [product for product in CATALOG if query_lower in product.name.lower() or any(query_lower in tag for tag in product.tags)]
