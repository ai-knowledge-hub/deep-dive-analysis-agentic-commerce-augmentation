"""Heuristic optimizer for simulation sandbox."""

from __future__ import annotations

from typing import Dict, List

from modules.simulation.domain import SimulationProduct


def optimize_product(
    product: SimulationProduct, missing_signals: List[str]
) -> Dict[str, str]:
    """Return an optimized representation suggestion."""
    before = product.description or product.name
    if not missing_signals:
        return {
            "id": product.id,
            "name": product.name,
            "before": before,
            "after": before,
        }

    signals = ", ".join(missing_signals[:3])
    suffix = f" Designed to address: {signals}."
    after = before.rstrip(".") + "." + suffix
    return {
        "id": product.id,
        "name": product.name,
        "before": before,
        "after": after,
    }


__all__ = ["optimize_product"]
