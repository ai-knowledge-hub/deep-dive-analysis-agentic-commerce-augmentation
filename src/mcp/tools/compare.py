"""MCP tool wrapper for the compare primitive."""

from __future__ import annotations

from src.products.compare import compare as compare_products
from src.products.search import search


def run(ids: list[str]) -> dict:
    catalog = search("")
    id_to_product = {product.id: product for product in catalog}
    selected = [id_to_product[_id] for _id in ids if _id in id_to_product]
    return {"comparison": compare_products(selected)}
