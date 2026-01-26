"""Gap analysis for simulation sandbox."""

from __future__ import annotations

import os
import re
from typing import Dict, List, Tuple

from domain.simulation import gap_analysis as domain_gap
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
    tokens = domain_gap.tokenize(goal)
    product_text = _product_text(product)
    product_tokens = domain_gap.tokens_for_product_text(product_text)

    matched, missing = _matched_and_missing(goal, tokens, product, list(product_tokens))

    winner_matched: List[str] | None = None
    if winner and winner.id != product.id:
        winner_tokens = domain_gap.tokens_for_product_text(_product_text(winner))
        winner_matched, _ = _matched_and_missing(
            goal, tokens, winner, list(winner_tokens)
        )

    return domain_gap.analyze_gap_tokens(
        goal=goal,
        product_id=product.id,
        score=score,
        product_text_tokens=product_tokens,
        winner_id=winner.id if winner else None,
        winner_matched_tokens=winner_matched,
        matched_tokens=matched,
    )


def derive_lessons(goal: str, gaps: List[Dict[str, object]]) -> List[str]:
    return domain_gap.derive_lessons(goal, gaps)


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
    return domain_gap.tokenize(text)


def _summary(goal: str, missing: List[str], severity: str) -> str:
    return domain_gap.summary(goal, missing, severity)


__all__ = ["analyze_gap", "derive_lessons"]
