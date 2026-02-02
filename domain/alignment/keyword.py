from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set


def tokenize(text: str) -> List[str]:
    tokens = [token.strip() for token in re.split(r"[^a-z0-9]+", (text or "").lower())]
    stopwords = {
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
    return [token for token in tokens if token and token not in stopwords]


def product_tokens(product: Dict[str, Any]) -> Set[str]:
    text_sources: List[str] = [
        str(product.get("name") or ""),
        str(product.get("description") or ""),
        " ".join(product.get("tags") or []),
    ]
    if product.get("capabilities_enabled"):
        text_sources.append(" ".join(product.get("capabilities_enabled") or []))
    profile = product.get("intentionality_profile") or {}
    if isinstance(profile, dict):
        goals_served = profile.get("goals_served") or []
        outcomes = profile.get("outcomes_expected") or []
        text_sources.append(" ".join(goals_served))
        text_sources.append(" ".join(outcomes))
    return set(tokenize(" ".join([s for s in text_sources if s])))


def best_capability(product: Dict[str, Any], goal: str) -> Optional[str]:
    capabilities: Sequence[str] = product.get("capabilities_enabled") or []
    if not capabilities:
        return None
    goal_words = set((goal or "").lower().split())
    best_item = None
    best_overlap = -1
    for capability in capabilities:
        cap_words = set((capability or "").lower().split())
        overlap = len(goal_words & cap_words)
        if overlap > best_overlap:
            best_overlap = overlap
            best_item = capability
    return best_item or capabilities[0]


def match_goal_to_product(
    goal_tokens: Set[str], product: Dict[str, Any]
) -> Dict[str, Any]:
    tokens = product_tokens(product)
    category_missing = _missing_required_category(goal_tokens, tokens)
    if category_missing:
        return {
            "score": 0.0,
            "capabilities": [],
            "missing": sorted(goal_tokens - tokens) + [category_missing],
        }
    overlap = goal_tokens & tokens
    overlap_score = min(1.0, len(overlap) / max(len(goal_tokens), 1))

    capability_hits = [
        cap
        for cap in (product.get("capabilities_enabled") or [])
        if goal_tokens & set(tokenize(cap))
    ]
    tag_hits = [tag for tag in (product.get("tags") or []) if tag in goal_tokens]

    score = 0.2 + 0.6 * overlap_score
    if capability_hits:
        score += 0.15
    if tag_hits:
        score += 0.05
    score = min(score, 0.95)

    return {
        "score": score if overlap else 0.0,
        "capabilities": capability_hits,
        "missing": sorted(goal_tokens - tokens),
    }


def _missing_required_category(goal_tokens: Set[str], product_tokens_set: Set[str]) -> str | None:
    category_groups = [
        {"shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers", "footwear"},
        {"vest", "vests", "jacket", "jackets", "outerwear"},
        {"bag", "bags", "backpack", "backpacks"},
        {"headphone", "headphones", "earbud", "earbuds"},
    ]
    for group in category_groups:
        if goal_tokens & group:
            if not (product_tokens_set & group):
                # Return a representative token for messaging.
                return sorted(group)[0]
    return None


def alignment_explanation(
    *,
    goal: str,
    similarity_score: float,
    high_threshold: float,
    medium_threshold: float,
    capabilities_enabled: Sequence[str],
    matched_caps: Optional[Sequence[str]] = None,
    missing_signals: Optional[Sequence[str]] = None,
) -> str:
    if not goal:
        return "No goal match found."

    if similarity_score >= high_threshold:
        strength = "strongly"
    elif similarity_score >= medium_threshold:
        strength = "reasonably"
    else:
        strength = "weakly"

    matched = list(matched_caps or [])
    if not matched:
        goal_tokens = set(tokenize(goal))
        matched = [
            cap
            for cap in capabilities_enabled
            if goal_tokens and set(tokenize(cap)) and goal_tokens & set(tokenize(cap))
        ]

    capabilities = ", ".join((matched[:3] or list(capabilities_enabled)[:3]))
    if not capabilities:
        capabilities = "general use"

    missing = list(missing_signals or [])
    missing_text = ""
    if similarity_score < medium_threshold and missing:
        missing_text = f" Missing signals: {', '.join(missing[:2])}."

    return (
        f"This product {strength} matches '{goal}'. "
        f"Signals: {capabilities}. "
        f"Confidence: {similarity_score:.0%}."
        f"{missing_text}"
    )


def dedupe_keep_order(items: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out
