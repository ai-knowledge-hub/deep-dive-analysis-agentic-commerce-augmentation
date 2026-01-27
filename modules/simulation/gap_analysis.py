"""Gap analysis for simulation sandbox."""

from __future__ import annotations

import os
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
    product_dict = _product_to_dict(product)
    product_text = domain_gap.product_text(product_dict)
    product_tokens = domain_gap.tokens_for_product_text(product_text)

    matched, missing = _matched_and_missing(goal, tokens, product_dict, product_tokens)

    winner_matched: List[str] | None = None
    if winner and winner.id != product.id:
        winner_dict = _product_to_dict(winner)
        winner_text = domain_gap.product_text(winner_dict)
        winner_tokens = domain_gap.tokens_for_product_text(winner_text)
        winner_matched, _ = _matched_and_missing(goal, tokens, winner_dict, winner_tokens)

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


def _product_to_dict(product: Product) -> Dict[str, object]:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "tags": product.tags or [],
        "capabilities_enabled": product.capabilities_enabled or [],
        "intentionality_profile": product.intentionality_profile or {},
        "confidence": product.confidence,
    }


def _semantic_match(
    goal: str, tokens: List[str], product: Dict[str, object]
) -> Tuple[List[str], List[str]] | None:
    if not tokens or not goal:
        return [], []
    if not embedding_available():
        return None
    phrases = domain_gap.product_phrases(product)
    if not phrases:
        return None

    try:
        embeddings = embed_batch([goal] + tokens + phrases)
    except Exception:
        return None

    goal_embedding = embeddings[0]
    token_embeddings = embeddings[1 : 1 + len(tokens)]
    phrase_embeddings = embeddings[1 + len(tokens) :]
    return domain_gap.semantic_match_from_embeddings(
        goal=goal,
        goal_tokens=tokens,
        phrases=phrases,
        goal_embedding=goal_embedding,
        token_embeddings=token_embeddings,
        phrase_embeddings=phrase_embeddings,
        batch_cosine_similarity=batch_cosine_similarity,
        phrase_threshold=_PHRASE_THRESHOLD,
        token_threshold=_TOKEN_THRESHOLD,
    )


def _matched_and_missing(
    goal: str,
    tokens: List[str],
    product: Dict[str, object],
    product_tokens: set[str],
) -> Tuple[List[str], List[str]]:
    semantic = _semantic_match(goal, tokens, product)
    if semantic:
        return semantic
    return domain_gap.matched_and_missing_token_fallback(
        goal_tokens=tokens, product_tokens=product_tokens
    )


__all__ = ["analyze_gap", "derive_lessons"]
