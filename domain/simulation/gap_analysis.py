from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence, Set

from domain.alignment.keyword import dedupe_keep_order, tokenize


def product_text(product: Dict[str, Any]) -> str:
    parts: List[str] = [
        str(product.get("name") or ""),
        str(product.get("description") or ""),
    ]
    tags = product.get("tags") or []
    if tags:
        parts.append(" ".join([str(t) for t in tags]))
    capabilities = product.get("capabilities_enabled") or []
    if capabilities:
        parts.append(" ".join([str(c) for c in capabilities]))
    profile = product.get("intentionality_profile") or {}
    if isinstance(profile, dict):
        goals = profile.get("goals_served") or []
        outcomes = profile.get("outcomes_expected") or []
        if goals:
            parts.append(" ".join([str(g) for g in goals]))
        if outcomes:
            parts.append(" ".join([str(o) for o in outcomes]))
    return " ".join([p for p in parts if p]).strip()


def product_phrases(product: Dict[str, Any]) -> List[str]:
    phrases: List[str] = []
    name = str(product.get("name") or "").strip()
    if name:
        phrases.append(name)

    description = str(product.get("description") or "").strip()
    if description:
        phrases.extend(
            [s.strip() for s in re.split(r"[.!?]+", description) if s.strip()]
        )

    tags = product.get("tags") or []
    if tags:
        phrases.append(" ".join([str(t) for t in tags]))

    capabilities = product.get("capabilities_enabled") or []
    if capabilities:
        phrases.append(" ".join([str(c) for c in capabilities]))

    profile = product.get("intentionality_profile") or {}
    if isinstance(profile, dict):
        goals = profile.get("goals_served") or []
        outcomes = profile.get("outcomes_expected") or []
        if goals:
            phrases.append(" ".join([str(g) for g in goals]))
        if outcomes:
            phrases.append(" ".join([str(o) for o in outcomes]))

    return [p for p in phrases if p]


def analyze_gap_tokens(
    *,
    goal: str,
    product_id: str,
    score: float,
    product_text_tokens: Set[str],
    winner_id: str | None = None,
    winner_matched_tokens: Sequence[str] | None = None,
    matched_tokens: Sequence[str] | None = None,
) -> Dict[str, Any]:
    goal_tokens = set(tokenize(goal))
    matched = sorted(goal_tokens & product_text_tokens)
    missing = sorted(goal_tokens - product_text_tokens)

    if matched_tokens is not None:
        matched = list(matched_tokens)
    winner_signals: List[str] = []
    if winner_id and winner_matched_tokens is not None:
        winner_signals = [
            signal for signal in winner_matched_tokens if signal not in matched
        ][:3]

    winner_summary = None
    if winner_id and winner_signals:
        winner_summary = (
            f"Winner highlights {', '.join(winner_signals)} for '{goal}', "
            "while this product doesn't frame it that way."
        )

    severity = severity_for_score(score)
    return {
        "product_id": product_id,
        "goal": goal,
        "score": round(score, 3),
        "matched_signals": matched[:5],
        "missing_signals": missing[:5],
        "winner_id": winner_id,
        "winner_signals": winner_signals,
        "competitor_summary": winner_summary,
        "severity": severity,
        "summary": summary(goal, missing, severity),
    }


def severity_for_score(score: float) -> str:
    if score < 0.35:
        return "high"
    if score < 0.55:
        return "medium"
    return "low"


def summary(goal: str, missing: Sequence[str], severity: str) -> str:
    if not missing:
        return f"Clear coverage of '{goal}'."
    missing_list = ", ".join(list(missing)[:3])
    return f"{severity.title()} gap: missing signals for {missing_list}."


def derive_lessons(goal: str, gaps: List[Dict[str, object]]) -> List[str]:
    lessons: List[str] = []
    for gap in gaps:
        winner_signals = gap.get("winner_signals") or []
        if winner_signals:
            lessons.append(
                f"For '{goal}', emphasize {', '.join(list(winner_signals)[:2])} explicitly."
            )
        missing_signals = gap.get("missing_signals") or []
        if missing_signals:
            lessons.append(
                f"Reframe specs into outcomes: {', '.join(list(missing_signals)[:2])}."
            )
    return dedupe_keep_order([str(item) for item in lessons])[:3]


def tokens_for_product_text(text: str) -> Set[str]:
    return set(tokenize(text))


def matched_and_missing_token_fallback(
    *, goal_tokens: Sequence[str], product_tokens: Set[str]
) -> tuple[List[str], List[str]]:
    tokens = [t for t in goal_tokens if t]
    matched = sorted(set(tokens) & set(product_tokens))
    missing = sorted(set(tokens) - set(product_tokens))
    return matched, missing


def semantic_match_from_embeddings(
    *,
    goal: str,
    goal_tokens: Sequence[str],
    phrases: Sequence[str],
    goal_embedding: Sequence[float],
    token_embeddings: Sequence[Sequence[float]],
    phrase_embeddings: Sequence[Sequence[float]],
    batch_cosine_similarity: Any,
    phrase_threshold: float,
    token_threshold: float,
) -> tuple[List[str], List[str]]:
    tokens = [t for t in goal_tokens if t]
    if not goal or not tokens or not phrases:
        return [], []
    if not phrase_embeddings:
        return tokens[:5], []

    phrase_similarities = batch_cosine_similarity(goal_embedding, phrase_embeddings)
    if phrase_similarities and max(phrase_similarities) >= phrase_threshold:
        return tokens[:5], []

    matched: List[str] = []
    missing: List[str] = []
    for token, token_embedding in zip(tokens, token_embeddings):
        similarities = batch_cosine_similarity(token_embedding, phrase_embeddings)
        if similarities and max(similarities) >= token_threshold:
            matched.append(token)
        else:
            missing.append(token)
    return matched, missing


__all__ = [
    "analyze_gap_tokens",
    "derive_lessons",
    "matched_and_missing_token_fallback",
    "product_phrases",
    "product_text",
    "semantic_match_from_embeddings",
    "severity_for_score",
    "summary",
    "tokens_for_product_text",
]
