"""Application service for intentionality profiling.

Orchestrates optional LLM enrichment while keeping parsing/pure logic in domain.
"""

from __future__ import annotations

from typing import Callable

from domain.intentionality.profiling import base_profile, build_prompt, parse_profile_json
from domain.intentionality.types import IntentionalityProfile
from infrastructure.llm.gateway import generate


def _intentionality_prompt_template() -> str:
    # Keep prompt local to avoid depending on `modules/*` or `shared/*` directly.
    return """You are a product intentionality profiler.
Your job is to translate product specs into intent-legible capabilities and outcomes.

Return JSON with:
- capabilities_enabled: list of capability phrases
- goals_served: list of human goals this supports
- prerequisites: list of prerequisites or constraints
- outcomes_expected: list of outcomes the user can expect
- context_fit: map of context labels to fit scores (0.0-1.0)
"""


def build_profile(
    product,
    *,
    generate_fn: Callable[[str], str] | None = None,
) -> IntentionalityProfile:
    """Build an intent-legible profile for a product.

    `product` is expected to be `modules.commerce.domain.Product`-like.
    """
    fallback = base_profile(
        product_id=product.id,
        capabilities_enabled=list(getattr(product, "capabilities_enabled", []) or []),
        tags=list(getattr(product, "tags", []) or []),
        description=getattr(product, "description", None),
        context_fit=dict(getattr(product, "intent_scores", {}) or {}),
    )

    if not generate_fn:
        return fallback

    prompt = build_prompt(
        template=_intentionality_prompt_template(),
        name=getattr(product, "name", ""),
        description=getattr(product, "description", None),
        capabilities=list(fallback.capabilities_enabled),
    )
    try:
        raw = generate_fn(prompt)
        return parse_profile_json(raw=raw, fallback=fallback)
    except Exception:
        return fallback


def build_profile_with_llm(product) -> IntentionalityProfile:
    return build_profile(product, generate_fn=lambda p: generate(p))


__all__ = ["build_profile", "build_profile_with_llm", "IntentionalityProfile"]

