"""Gap analysis for simulation sandbox."""

from __future__ import annotations

import re
from typing import Dict, List

from modules.commerce.domain import Product


def analyze_gap(goal: str, product: Product, score: float) -> Dict[str, object]:
    tokens = _tokenize(goal)
    product_tokens = _tokenize(_product_text(product))
    missing = sorted(set(tokens) - set(product_tokens))
    matched = sorted(set(tokens) & set(product_tokens))

    severity = "low"
    if score < 0.35:
        severity = "high"
    elif score < 0.55:
        severity = "medium"

    return {
        "product_id": product.id,
        "goal": goal,
        "score": round(score, 3),
        "matched_signals": matched[:5],
        "missing_signals": missing[:5],
        "severity": severity,
        "summary": _summary(goal, missing, severity),
    }


def _product_text(product: Product) -> str:
    parts: List[str] = [product.name, product.description]
    if product.tags:
        parts.append(" ".join(product.tags))
    if product.capabilities_enabled:
        parts.append(" ".join(product.capabilities_enabled))
    if product.intentionality_profile:
        parts.append(" ".join(product.intentionality_profile.get("goals_served") or []))
        parts.append(
            " ".join(product.intentionality_profile.get("outcomes_expected") or [])
        )
    return " ".join([part for part in parts if part])


def _tokenize(text: str) -> List[str]:
    tokens = [t for t in re.split(r"[^a-z0-9]+", text.lower()) if t]
    stop = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "your",
        "you",
        "from",
        "into",
        "when",
        "what",
        "how",
        "need",
        "needs",
        "want",
        "wants",
        "help",
        "best",
        "better",
        "more",
        "less",
        "not",
        "no",
        "new",
        "find",
        "get",
    }
    return [token for token in tokens if token not in stop]


def _summary(goal: str, missing: List[str], severity: str) -> str:
    if not missing:
        return f"Clear coverage of '{goal}'."
    missing_list = ", ".join(missing[:3])
    return f"{severity.title()} gap: missing signals for {missing_list}."


__all__ = ["analyze_gap"]
