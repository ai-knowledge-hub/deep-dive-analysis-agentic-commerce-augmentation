"""Compare a list of products by basic attributes."""

from __future__ import annotations

from typing import Iterable, List

from .schemas import Product


def compare(products: Iterable[Product]) -> str:
    lines = ["ID | Name | Price | Confidence | Source"]
    for product in products:
        lines.append(
            f"{product.id} | {product.name} | ${product.price} | {product.confidence:.2f} | {product.source}"
        )
    return "\n".join(lines)
