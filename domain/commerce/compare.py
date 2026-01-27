"""Pure formatting helpers for comparing products."""

from __future__ import annotations

from typing import Iterable

from domain.commerce.types import Product


def compare(products: Iterable[Product]) -> str:
    lines = ["ID | Name | Price | Confidence | Source"]
    for product in products:
        lines.append(
            f"{product.id} | {product.name} | ${product.price} | {product.confidence:.2f} | {product.source}"
        )
    return "\n".join(lines)


__all__ = ["compare"]
