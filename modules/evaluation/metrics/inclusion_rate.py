"""Metric functions for evaluating representation quality."""

from __future__ import annotations

from typing import List

from modules.commerce.domain import Product


def inclusion_rate(products: List[Product], required_capability: str) -> float:
    if not products:
        return 0.0
    hits = [
        product
        for product in products
        if required_capability in product.capabilities_enabled
    ]
    return len(hits) / len(products)
