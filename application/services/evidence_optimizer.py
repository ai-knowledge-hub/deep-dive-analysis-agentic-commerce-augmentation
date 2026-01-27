"""Application-layer evidence optimizer (before/after representation)."""

from __future__ import annotations

from typing import Dict, List

from domain.evidence.types import EvidenceProduct
from infrastructure.llm.gateway import generate
from infrastructure.llm.prompts import build_optimization_prompt
from modules.intentionality.profiling import build_profile

from application.services.evidence_normalizer import to_product


def optimize(
    evidence_products: List[EvidenceProduct],
    goals: List[str] | None = None,
    tone: str | None = None,
) -> List[Dict[str, object]]:
    optimized: List[Dict[str, object]] = []
    for evidence in evidence_products:
        product = to_product(evidence)
        profile = build_profile(product)
        optimized_text = (evidence.metadata or {}).get("optimized_description")
        after_text = optimized_text or _llm_optimize_description(
            name=product.name,
            description=product.description or product.name,
            goals=goals,
            tone=tone,
            price=product.price,
            signals=(profile.capabilities_enabled or []) + (profile.outcomes_expected or []),
        )
        optimized.append(
            {
                "id": evidence.id,
                "name": evidence.name,
                "before": product.description,
                "after": after_text,
                "capabilities": profile.capabilities_enabled,
                "outcomes": profile.outcomes_expected,
                "goals": goals or profile.goals_served,
            }
        )
    return optimized


def _llm_optimize_description(
    *,
    name: str,
    description: str,
    signals: List[str],
    goals: List[str] | None = None,
    tone: str | None = None,
    price: float | None = None,
) -> str:
    merged: List[str] = []
    merged.extend(signals)
    if goals:
        merged.extend(goals)
    signals_text = ", ".join([s for s in merged if s][:5]) if merged else "intent clarity"
    prompt = build_optimization_prompt(
        name=name,
        description=description,
        signals=signals_text,
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
    # fallback: keep original description if LLM not available
    return description


__all__ = ["optimize"]

