"""Semantic goal-product alignment using embeddings.

This module assesses how well products align with user-declared goals
using semantic similarity (embeddings) rather than simple string matching.
This supports intent-alignment scoring for brand discovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from domain.alignment import keyword as domain_keyword
from domain.alignment import scoring as domain_scoring
from modules.commerce.domain import Product
from modules.alignment.domain import AlignmentScore, AlignmentSummary

logger = logging.getLogger(__name__)

# Similarity thresholds
HIGH_ALIGNMENT_THRESHOLD = 0.7  # Strong semantic match
MEDIUM_ALIGNMENT_THRESHOLD = 0.5  # Reasonable match
LOW_ALIGNMENT_THRESHOLD = 0.3  # Weak but possible match


@dataclass
class ProductAlignment:
    """Alignment details for a single product."""

    product_id: str
    product_name: str
    overall_score: float
    goal_scores: Dict[str, float]  # goal -> similarity score
    best_matching_goal: Optional[str]
    best_matching_capability: Optional[str]
    confidence: float


def assess(
    goals: List[str],
    products: List[Product],
    use_semantic: bool = True,
) -> AlignmentSummary:
    """Assess how well products align with user goals.

    Args:
        goals: List of user-declared goals (e.g., "reduce back pain", "learn Python")
        products: List of products to evaluate
        use_semantic: Whether to use semantic similarity (True) or fall back to keywords

    Returns:
        AlignmentSummary with alignment scores and supporting products
    """
    if not goals:
        return AlignmentSummary(
            score=0.0,
            aligned_goals=[],
            misaligned_goals=[],
            supporting_products=[],
            confidence_summary={
                "average_confidence": 0.0,
                "aligned_goal_confidence": {},
            },
        )

    if not products:
        return AlignmentSummary(
            score=0.0,
            aligned_goals=[],
            misaligned_goals=goals,
            supporting_products=[],
            confidence_summary={
                "average_confidence": 0.0,
                "aligned_goal_confidence": {},
            },
        )

    # Try semantic alignment first, fall back to keyword matching
    from shared.llm.embeddings import embedding_available

    if use_semantic and embedding_available():
        try:
            return _semantic_assess(goals, products)
        except Exception as e:
            logger.warning(f"Semantic alignment failed, falling back to keywords: {e}")
            return _keyword_assess(goals, products)
    else:
        return _keyword_assess(goals, products)


def score_products(
    goals: List[str],
    products: List[Product],
    use_semantic: bool = True,
) -> List[AlignmentScore]:
    """Score each product against the provided goals."""
    if not goals or not products:
        return []

    from shared.llm.embeddings import embedding_available

    if use_semantic and embedding_available():
        try:
            return _semantic_score_products(goals, products)
        except Exception as e:
            logger.warning(f"Semantic per-product scoring failed, falling back: {e}")
            return _keyword_score_products(goals, products)

    return _keyword_score_products(goals, products)


def _semantic_assess(goals: List[str], products: List[Product]) -> AlignmentSummary:
    """Assess alignment using semantic similarity (embeddings)."""
    from shared.llm.embeddings import (
        get_embedding_provider,
        cosine_similarity,
    )

    provider = get_embedding_provider()

    product_dicts = [_product_to_dict(p) for p in products]
    product_texts = [domain_scoring.build_product_semantic_text(p) for p in product_dicts]

    all_texts = list(goals) + product_texts
    embeddings = provider.embed_batch(all_texts)

    goal_embeddings = embeddings[: len(goals)]
    product_embeddings = embeddings[len(goals) :]

    return domain_scoring.semantic_assess(
        goals=goals,
        products=product_dicts,
        goal_embeddings=goal_embeddings,
        product_embeddings=product_embeddings,
        cosine_similarity=cosine_similarity,
        provider_name=provider.provider_name,
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


def _keyword_assess(goals: List[str], products: List[Product]) -> AlignmentSummary:
    """Fallback: Assess alignment using keyword matching (original implementation)."""
    return domain_scoring.keyword_assess(
        goals=goals,
        products=[_product_to_dict(p) for p in products],
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


def _semantic_score_products(
    goals: List[str], products: List[Product]
) -> List[AlignmentScore]:
    """Score products using semantic similarity (embeddings)."""
    from shared.llm.embeddings import (
        get_embedding_provider,
        cosine_similarity,
    )

    provider = get_embedding_provider()

    product_dicts = [_product_to_dict(p) for p in products]
    product_texts = [domain_scoring.build_product_semantic_text(p) for p in product_dicts]
    all_texts = goals + product_texts
    embeddings = provider.embed_batch(all_texts)

    goal_embeddings = embeddings[: len(goals)]
    product_embeddings = embeddings[len(goals) :]

    try:
        from modules.intent.embeddings import upsert_intent_embedding
        from modules.commerce.embeddings import upsert_product_embedding

        for goal, embedding in zip(goals, goal_embeddings):
            upsert_intent_embedding(goal, embedding)
        for product, embedding in zip(products, product_embeddings):
            upsert_product_embedding(product.id, embedding)
    except Exception:
        pass

    return domain_scoring.semantic_score_products(
        goals=goals,
        products=product_dicts,
        goal_embeddings=goal_embeddings,
        product_embeddings=product_embeddings,
        cosine_similarity=cosine_similarity,
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


def _keyword_score_products(
    goals: List[str], products: List[Product]
) -> List[AlignmentScore]:
    """Score products using keyword overlap heuristics."""
    return domain_scoring.keyword_score_products(
        goals=goals,
        products=[_product_to_dict(p) for p in products],
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


def _product_to_dict(product: Product) -> Dict[str, object]:
    return {
        "id": product.id,
        "name": product.name,
        "description": product.description,
        "category": product.category,
        "tags": product.tags or [],
        "capabilities_enabled": product.capabilities_enabled or [],
        "intentionality_profile": product.intentionality_profile or {},
        "confidence": product.confidence,
    }


def _build_product_semantic_text(product: Product) -> str:
    """Compatibility shim for older tests/usage.

    Canonical implementation lives in `domain.alignment.scoring.build_product_semantic_text`.
    """
    return domain_scoring.build_product_semantic_text(_product_to_dict(product))


def get_alignment_explanation(
    goal: str,
    product: Product,
    similarity_score: float,
    matched_caps: List[str] | None = None,
    missing_signals: List[str] | None = None,
) -> str:
    """Generate a human-readable explanation of goal-product alignment.

    Used for transparency in recommendations.
    """
    return domain_keyword.alignment_explanation(
        goal=goal,
        similarity_score=similarity_score,
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
        capabilities_enabled=product.capabilities_enabled or [],
        matched_caps=matched_caps,
        missing_signals=missing_signals,
    )


__all__ = [
    "assess",
    "score_products",
    "get_alignment_explanation",
    "ProductAlignment",
    "HIGH_ALIGNMENT_THRESHOLD",
    "MEDIUM_ALIGNMENT_THRESHOLD",
    "LOW_ALIGNMENT_THRESHOLD",
]
