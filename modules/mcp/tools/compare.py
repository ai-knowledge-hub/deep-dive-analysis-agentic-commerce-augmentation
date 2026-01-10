"""MCP tool wrapper for the product comparison primitive."""

from __future__ import annotations

from modules.commerce.compare import compare as compare_products
from modules.commerce.search import search


def run(ids: list[str]) -> dict:
    """Compare selected products and return metadata alongside the table."""
    catalog = search("")
    id_to_product = {product.id: product for product in catalog}
    selected = [id_to_product[_id] for _id in ids if _id in id_to_product]
    comparison = compare_products(selected)
    return {
        "comparison": comparison,
        "metadata": [
            {
                "id": product.id,
                "confidence": product.confidence,
                "source": product.source,
                "merchant_name": product.merchant_name,
            }
            for product in selected
        ],
    }


__all__ = ["run"]
