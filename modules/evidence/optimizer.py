"""Optimization helpers for evidence representations."""

from __future__ import annotations

from typing import Dict, List

from modules.commerce.domain import Product
from modules.evidence.domain import EvidenceProduct
from modules.evidence.normalizer import to_product
from modules.intentionality.profiling import build_profile


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
        after_text = optimized_text or _format_intent_legible_description(
            product, profile
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


__all__ = ["optimize"]
