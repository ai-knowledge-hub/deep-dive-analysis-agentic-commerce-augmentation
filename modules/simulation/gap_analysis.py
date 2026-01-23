"""Gap analysis for simulation sandbox."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

from modules.commerce.domain import Product
from shared.llm.embeddings import (
    batch_cosine_similarity,
    embed_batch,
    embedding_available,
)

_PHRASE_THRESHOLD = float(os.getenv("SIMULATION_GAP_PHRASE_THRESHOLD", "0.76"))
_TOKEN_THRESHOLD = float(os.getenv("SIMULATION_GAP_TOKEN_THRESHOLD", "0.74"))


def analyze_gap(
    goal: str,
    product: Product,
    score: float,
    winner: Product | None = None,
) -> Dict[str, object]:
    tokens = _tokenize(goal)
    product_text = _product_text(product)
    product_tokens = _tokenize(product_text)

    matched: List[str]
    missing: List[str]

    matched, missing = _matched_and_missing(goal, tokens, product, product_tokens)

    winner_summary = None
    winner_signals: List[str] = []
    if winner and winner.id != product.id:
        winner_tokens = _tokenize(_product_text(winner))
        winner_matched, _ = _matched_and_missing(goal, tokens, winner, winner_tokens)
        winner_signals = [signal for signal in winner_matched if signal not in matched][
            :3
        ]
        if winner_signals:
            winner_summary = (
                f"Winner highlights {', '.join(winner_signals)} "
                f"for '{goal}', while this product doesn't frame it that way."
            )

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
        "winner_id": winner.id if winner else None,
        "winner_signals": winner_signals,
        "competitor_summary": winner_summary,
        "severity": severity,
        "summary": _summary(goal, missing, severity),
    }


def derive_lessons(goal: str, gaps: List[Dict[str, object]]) -> List[str]:
    lessons: List[str] = []
    for gap in gaps:
        winner_signals = gap.get("winner_signals") or []
        if winner_signals:
            lessons.append(
                f"For '{goal}', emphasize {', '.join(winner_signals[:2])} explicitly."
            )
        missing_signals = gap.get("missing_signals") or []
        if missing_signals:
            lessons.append(
                f"Reframe specs into outcomes: {', '.join(missing_signals[:2])}."
            )
    deduped = list(dict.fromkeys([lesson for lesson in lessons if lesson]))
    return deduped[:3]


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


def _product_phrases(product: Product) -> List[str]:
    phrases: List[str] = []
    if product.name:
        phrases.append(product.name)
    if product.description:
        phrases.extend(
            [s.strip() for s in re.split(r"[.!?]+", product.description) if s.strip()]
        )
    if product.tags:
        phrases.append(" ".join(product.tags))
    if product.capabilities_enabled:
        phrases.append(" ".join(product.capabilities_enabled))
    if product.intentionality_profile:
        goals = product.intentionality_profile.get("goals_served") or []
        outcomes = product.intentionality_profile.get("outcomes_expected") or []
        if goals:
            phrases.append(" ".join(goals))
        if outcomes:
            phrases.append(" ".join(outcomes))
    return [phrase for phrase in phrases if phrase]


def _semantic_match(
    goal: str, tokens: List[str], product: Product
) -> Tuple[List[str], List[str]] | None:
    if not tokens or not goal:
        return [], []
    if not embedding_available():
        return None
    phrases = _product_phrases(product)
    if not phrases:
        return None

    try:
        embeddings = embed_batch([goal] + tokens + phrases)
    except Exception:
        return None

    goal_embedding = embeddings[0]
    token_embeddings = embeddings[1 : 1 + len(tokens)]
    phrase_embeddings = embeddings[1 + len(tokens) :]

    phrase_similarities = batch_cosine_similarity(goal_embedding, phrase_embeddings)
    if phrase_similarities and max(phrase_similarities) >= _PHRASE_THRESHOLD:
        return tokens[:5], []
    matched: List[str] = []
    missing: List[str] = []
    for token, token_embedding in zip(tokens, token_embeddings):
        similarities = batch_cosine_similarity(token_embedding, phrase_embeddings)
        if similarities and max(similarities) >= _TOKEN_THRESHOLD:
            matched.append(token)
        else:
            missing.append(token)
    return matched, missing


def _matched_and_missing(
    goal: str,
    tokens: List[str],
    product: Product,
    product_tokens: List[str],
) -> Tuple[List[str], List[str]]:
    semantic = _semantic_match(goal, tokens, product)
    if semantic:
        return semantic
    missing = sorted(set(tokens) - set(product_tokens))
    matched = sorted(set(tokens) & set(product_tokens))
    return matched, missing


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


__all__ = ["analyze_gap", "derive_lessons"]
