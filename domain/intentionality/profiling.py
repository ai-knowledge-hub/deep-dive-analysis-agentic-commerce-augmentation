"""Pure intentionality profiling helpers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from domain.intentionality.types import IntentionalityProfile


def first_sentence(text: str) -> str:
    if not text:
        return ""
    parts = text.split(".")
    return parts[0].strip() if parts else text.strip()


def base_profile(
    *,
    product_id: str,
    capabilities_enabled: List[str],
    tags: List[str] | None = None,
    description: str | None = None,
    context_fit: Dict[str, float] | None = None,
) -> IntentionalityProfile:
    capabilities = list(capabilities_enabled or [])
    if not capabilities:
        capabilities = list(tags or [])

    goals_served = list(dict.fromkeys(capabilities))
    outcomes: List[str] = []
    sentence = first_sentence(description or "")
    if sentence:
        outcomes.append(sentence)

    return IntentionalityProfile(
        product_id=product_id,
        capabilities_enabled=capabilities,
        goals_served=goals_served,
        prerequisites=[],
        outcomes_expected=outcomes,
        context_fit=dict(context_fit or {}),
    )


def parse_profile_json(
    *,
    raw: str,
    fallback: IntentionalityProfile,
) -> IntentionalityProfile:
    try:
        payload = json.loads(raw)
    except Exception:
        payload = {}

    return IntentionalityProfile(
        product_id=fallback.product_id,
        capabilities_enabled=payload.get("capabilities_enabled", fallback.capabilities_enabled),
        goals_served=payload.get("goals_served", fallback.goals_served),
        prerequisites=payload.get("prerequisites", fallback.prerequisites),
        outcomes_expected=payload.get("outcomes_expected", fallback.outcomes_expected),
        context_fit=payload.get("context_fit", fallback.context_fit),
    )


def build_prompt(
    *,
    template: str,
    name: str,
    description: str | None,
    capabilities: List[str],
) -> str:
    return (
        f"{template}\n\n"
        f"Product name: {name}\n"
        f"Description: {description or ''}\n"
        f"Capabilities: {', '.join(capabilities)}"
    )


__all__ = ["base_profile", "build_prompt", "first_sentence", "parse_profile_json"]

