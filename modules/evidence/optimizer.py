"""Optimization helpers for evidence representations."""

from __future__ import annotations

from typing import Dict, List

from modules.commerce.domain import Product
from modules.evidence.domain import EvidenceProduct
from modules.evidence.normalizer import to_product
from modules.intentionality.profiling import build_profile
from shared.llm.gateway import generate
from shared.llm.prompts import build_optimization_prompt


def optimize(
    evidence_products: List[EvidenceProduct],
    goals: List[str] | None = None,
) -> List[Dict[str, object]]:
    """Return before/after framing pairs for evidence products."""
    optimized: List[Dict[str, object]] = []
    for evidence in evidence_products:
        product = to_product(evidence)
        profile = build_profile(product)
        optimized_text = evidence.metadata.get("optimized_description")
        after_text = optimized_text or _llm_optimize_description(
            product, profile, goals
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


def _format_intent_legible_description(product: Product, profile) -> str:
    capabilities = profile.capabilities_enabled or []
    outcomes = profile.outcomes_expected or []
    pieces: List[str] = []
    if capabilities:
        pieces.append(f"Enables: {', '.join(capabilities[:3])}.")
    if outcomes:
        pieces.append(f"Outcome: {outcomes[0]}.")
    if product.description:
        pieces.append(product.description)
    return " ".join(pieces).strip()


def _llm_optimize_description(
    product: Product, profile, goals: List[str] | None = None
) -> str:
    signals: List[str] = []
    signals.extend(profile.capabilities_enabled or [])
    signals.extend(profile.outcomes_expected or [])
    if goals:
        signals.extend(goals)
    signals_text = ", ".join(signals[:5]) if signals else "intent clarity"
    prompt = build_optimization_prompt(
        name=product.name,
        description=product.description or product.name,
        signals=signals_text,
        price=product.price,
    )
    try:
        response = generate(prompt)
        cleaned = response.strip()
        if cleaned:
            return cleaned
    except Exception:
        pass
    return _format_intent_legible_description(product, profile)


__all__ = ["optimize"]
