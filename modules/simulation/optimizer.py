"""Heuristic optimizer for simulation sandbox."""

from __future__ import annotations

from typing import Dict, List

from shared.llm.gateway import generate
from shared.llm.prompts import build_optimization_prompt

from modules.simulation.domain import SimulationProduct


def optimize_product(
    product: SimulationProduct,
    missing_signals: List[str],
    tone: str | None = None,
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

    signals = ", ".join(missing_signals[:4])
    after = _llm_optimize_description(
        before=before,
        name=product.name,
        signals=signals,
        price=product.price,
        tone=tone,
    )
    return {
        "id": product.id,
        "name": product.name,
        "before": before,
        "after": after,
    }


def _llm_optimize_description(
    before: str,
    name: str,
    signals: str,
    price: float | None = None,
    tone: str | None = None,
) -> str:
    prompt = build_optimization_prompt(
        name=name,
        description=before,
        signals=signals,
        price=price,
        tone=tone,
    )
    try:
        response = generate(prompt)
        cleaned = response.strip()
        if cleaned:
            return cleaned
    except Exception:
        pass

    suffix = f" Focused on {signals}."
    return before.rstrip(".") + "." + suffix


__all__ = ["optimize_product"]
