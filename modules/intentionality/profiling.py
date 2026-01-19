"""Intentionality profiling helpers."""

from __future__ import annotations

from typing import Callable, List

from modules.commerce.domain import Product
from modules.intentionality.domain import IntentionalityProfile
from modules.intentionality.prompts import INTENTIONALITY_PROFILE_PROMPT
from shared.llm.gateway import generate


def _first_sentence(text: str) -> str:
    if not text:
        return ""
    parts = text.split(".")
    return parts[0].strip() if parts else text.strip()


def build_profile(
    product: Product, generate_fn: Callable[[str], str] | None = None
) -> IntentionalityProfile:
    """Build an intent-legible profile for a product."""
    capabilities = list(product.capabilities_enabled or [])
    if not capabilities:
        capabilities = list(product.tags or [])

    goals_served = list(dict.fromkeys(capabilities))
    outcomes = []
    sentence = _first_sentence(product.description or "")
    if sentence:
        outcomes.append(sentence)

    context_fit = dict(product.intent_scores or {})

    if generate_fn:
        prompt = (
            f"{INTENTIONALITY_PROFILE_PROMPT}\n\n"
            f"Product name: {product.name}\n"
            f"Description: {product.description}\n"
            f"Capabilities: {', '.join(capabilities)}"
        )
        try:
            raw = generate_fn(prompt)
            return _parse_profile(product, raw, capabilities, outcomes, context_fit)
        except Exception:
            pass

    return IntentionalityProfile(
        product_id=product.id,
        capabilities_enabled=capabilities,
        goals_served=goals_served,
        prerequisites=[],
        outcomes_expected=outcomes,
        context_fit=context_fit,
    )


def build_profile_with_llm(product: Product) -> IntentionalityProfile:
    """Build a profile using the default LLM generator."""
    return build_profile(product, generate_fn=generate)


def _parse_profile(
    product: Product,
    raw: str,
    capabilities: List[str],
    outcomes: List[str],
    context_fit: dict,
) -> IntentionalityProfile:
    """Best-effort JSON parse with safe fallbacks."""
    import json

    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}

    return IntentionalityProfile(
        product_id=product.id,
        capabilities_enabled=payload.get("capabilities_enabled", capabilities),
        goals_served=payload.get("goals_served", capabilities),
        prerequisites=payload.get("prerequisites", []),
        outcomes_expected=payload.get("outcomes_expected", outcomes),
        context_fit=payload.get("context_fit", context_fit),
    )


__all__ = ["build_profile", "build_profile_with_llm"]
