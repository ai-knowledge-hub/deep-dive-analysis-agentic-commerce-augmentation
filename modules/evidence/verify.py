"""Verification helpers for evidence-first recommendations."""

from __future__ import annotations

from typing import List

from modules.commerce.domain import Product


def simulate_actual(products: List[Product], limit: int = 2) -> List[str]:
    """Simulate actual recommendations based on confidence ranking."""
    ordered = sorted(products, key=lambda p: p.confidence, reverse=True)
    return [product.id for product in ordered[:limit]]


def average_alignment(scores) -> float:
    if not scores:
        return 0.0
    return sum(score.score for score in scores) / len(scores)


__all__ = ["simulate_actual", "average_alignment"]
