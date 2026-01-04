"""Compare a list of products by basic attributes."""

from __future__ import annotations

from typing import List

from .schemas import Product


def compare(products: List[Product]) -> str:
    lines = ["ID | Name | Price"]
    for product in products:
        lines.append(f"{product.id} | {product.name} | ${product.price}")
    return "\n".join(lines)
