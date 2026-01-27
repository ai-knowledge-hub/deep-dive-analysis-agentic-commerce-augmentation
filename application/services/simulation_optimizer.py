"""Application-layer simulation optimizer.

This service generates "before → after" copy suggestions for simulation runs.
It is orchestration (LLM call + prompt template), not domain logic.
"""

from __future__ import annotations

from typing import Dict, List

from infrastructure.llm.gateway import generate
from infrastructure.llm.prompts import build_optimization_prompt
from modules.simulation.domain import SimulationProduct


def optimize_product(
    product: SimulationProduct,
    missing_signals: List[str],
    tone: str | None = None,
    lessons: List[str] | None = None,
) -> Dict[str, str]:
    before = product.description or product.name
    if not missing_signals:
        return {"id": product.id, "name": product.name, "before": before, "after": before}

    signals = ", ".join(missing_signals[:4])
    after = _llm_optimize_description(
        before=before,
        name=product.name,
        signals=signals,
        price=product.price,
        tone=tone,
        lessons=lessons,
    )
    return {"id": product.id, "name": product.name, "before": before, "after": after}


def _llm_optimize_description(
    *,
    before: str,
    name: str,
    signals: str,
    price: float | None = None,
    tone: str | None = None,
    lessons: List[str] | None = None,
) -> str:
    prompt = build_optimization_prompt(
        name=name,
        description=before,
        signals=signals,
        price=price,
        tone=tone,
        lessons=lessons,
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

