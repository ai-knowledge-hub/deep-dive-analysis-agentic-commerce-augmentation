"""Semantic goal-product alignment using embeddings.

This module assesses how well products align with user-declared goals
using semantic similarity (embeddings) rather than simple string matching.
This supports intent-alignment scoring for brand discovery.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from domain.alignment import keyword as domain_keyword
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

    # Prepare texts for embedding
    goal_texts = goals

    # Build product capability texts (what each product enables)
    product_texts: List[Tuple[Product, str]] = []
    for product in products:
        # Combine capabilities, description, and tags into a semantic representation
        capability_text = _build_product_semantic_text(product)
        product_texts.append((product, capability_text))

    # Generate embeddings
    all_texts = goal_texts + [pt[1] for pt in product_texts]
    embeddings = provider.embed_batch(all_texts)

    goal_embeddings = embeddings[: len(goals)]
    product_embeddings = embeddings[len(goals) :]

    # Calculate alignment scores
    aligned_goals: List[str] = []
    misaligned_goals: List[str] = []
    supporting_products: List[str] = []
    goal_confidence: Dict[str, float] = {}

    # For each goal, find if any product aligns
    for j, goal in enumerate(goals):
        goal_emb = goal_embeddings[j]
        max_similarity = 0.0
        best_products: List[str] = []

        for i, (product, _) in enumerate(product_texts):
            product_emb = product_embeddings[i]
            similarity = cosine_similarity(goal_emb, product_emb)

            if similarity >= MEDIUM_ALIGNMENT_THRESHOLD:
                best_products.append(product.id)
                max_similarity = max(max_similarity, similarity)

        if best_products:
            aligned_goals.append(goal)
            supporting_products.extend(best_products)
            # Weight confidence by similarity and product confidence
            avg_product_confidence = _average_confidence(
                [p for p in products if p.id in best_products]
            )
            goal_confidence[goal] = max_similarity * avg_product_confidence
        else:
            misaligned_goals.append(goal)

    # Deduplicate supporting products
    supporting_products = list(dict.fromkeys(supporting_products))

    # Calculate overall score
    if not goals:
        base_score = 0.0
    else:
        base_score = len(aligned_goals) / len(goals)

    # Weight by confidence
    confidence_weight = (
        sum(goal_confidence.values()) / max(len(goal_confidence), 1)
        if goal_confidence
        else 0.0
    )
    weighted_score = round(base_score * (0.6 + 0.4 * confidence_weight), 3)

    confidence_summary: Dict[str, float | Dict[str, float]] = {
        "average_confidence": round(_average_confidence(products), 2),
        "aligned_goal_confidence": {
            goal: round(score, 3) for goal, score in goal_confidence.items()
        },
        "embedding_provider": provider.provider_name,
        "alignment_method": "semantic",
    }

    return AlignmentSummary(
        score=weighted_score,
        aligned_goals=aligned_goals,
        misaligned_goals=misaligned_goals,
        supporting_products=supporting_products,
        confidence_summary=confidence_summary,
    )


def _keyword_assess(goals: List[str], products: List[Product]) -> AlignmentSummary:
    """Fallback: Assess alignment using keyword matching (original implementation)."""
    aligned: List[str] = []
    supporting_products: List[str] = []
    goal_confidence: Dict[str, float] = {}

    for goal in goals:
        normalized = goal.lower()
        goal_tokens = set(normalized.split())
        goal_products = [
            product
            for product in products
            if any(
                goal_tokens & set(capability.lower().split())
                for capability in product.capabilities_enabled
            )
            or any(tag in normalized or normalized in tag for tag in product.tags)
        ]
        if goal_products:
            aligned.append(goal)
            supporting_products.extend(product.id for product in goal_products)
            goal_confidence[goal] = _average_confidence(goal_products)

    misaligned = [goal for goal in goals if goal not in aligned]
    base_score = len(aligned) / max(len(goals), 1)
    confidence_weight = (
        sum(goal_confidence.values()) / max(len(goal_confidence), 1)
        if goal_confidence
        else 0.0
    )
    weighted_score = round(base_score * (0.7 + 0.3 * confidence_weight), 3)
    confidence_summary: Dict[str, float | Dict[str, float]] = {
        "average_confidence": round(_average_confidence(products), 2)
        if products
        else 0.0,
        "aligned_goal_confidence": {
            goal: round(score, 2) for goal, score in goal_confidence.items()
        },
        "alignment_method": "keyword",
    }

    return AlignmentSummary(
        score=weighted_score,
        aligned_goals=aligned,
        misaligned_goals=misaligned,
        supporting_products=list(dict.fromkeys(supporting_products)),
        confidence_summary=confidence_summary,
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

    product_texts = [_build_product_semantic_text(product) for product in products]
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

    scores: List[AlignmentScore] = []
    for product, product_emb in zip(products, product_embeddings):
        best_score = 0.0
        best_goal = None
        for goal, goal_emb in zip(goals, goal_embeddings):
            similarity = cosine_similarity(goal_emb, product_emb)
            if similarity > best_score:
                best_score = similarity
                best_goal = goal
        best_capability = _get_best_capability(product, best_goal or "")
        missing_signals = _missing_signals(best_goal or "", product)
        reasoning = (
            get_alignment_explanation(
                best_goal,
                product,
                best_score,
                [best_capability] if best_capability else [],
                missing_signals,
            )
            if best_goal
            else "No goal match found."
        )
        scores.append(
            AlignmentScore(
                product_id=product.id,
                score=round(best_score, 3),
                matched_capabilities=[cap for cap in [best_capability] if cap],
                alignment_reasoning=reasoning,
                confidence=round(product.confidence, 2),
                low_confidence=best_score < MEDIUM_ALIGNMENT_THRESHOLD,
            )
        )
    return scores


def _keyword_score_products(
    goals: List[str], products: List[Product]
) -> List[AlignmentScore]:
    """Score products using keyword overlap heuristics."""
    scores: List[AlignmentScore] = []
    for product in products:
        best_goal = None
        best_score = 0.0
        matched_caps: List[str] = []
        for goal in goals:
            goal_tokens = set(domain_keyword.tokenize(goal))
            if not goal_tokens:
                continue
            match = _match_goal_to_product(goal_tokens, product)
            if match["score"] > best_score:
                best_score = match["score"]
                best_goal = goal
                matched_caps = match["capabilities"]
        best_capability = _get_best_capability(product, best_goal or "")
        matched_caps = matched_caps or [cap for cap in [best_capability] if cap]
        missing_signals = match["missing"] if best_goal else []
        reasoning = (
            get_alignment_explanation(
                best_goal, product, best_score, matched_caps, missing_signals
            )
            if best_goal
            else "No goal match found."
        )
        scores.append(
            AlignmentScore(
                product_id=product.id,
                score=round(best_score, 3),
                matched_capabilities=list(dict.fromkeys(matched_caps)),
                alignment_reasoning=reasoning,
                confidence=round(product.confidence, 2),
                low_confidence=best_score < MEDIUM_ALIGNMENT_THRESHOLD,
            )
        )
    return scores


def _build_product_semantic_text(product: Product) -> str:
    """Build a semantic text representation of a product for embedding.

    Combines capabilities, description, and tags into a text that
    captures what the product enables and who it's for.
    """
    parts = []

    # Add capabilities (most important for goal alignment)
    if product.capabilities_enabled:
        capabilities = ", ".join(product.capabilities_enabled)
        parts.append(f"This product enables: {capabilities}")

    # Add description
    if product.description:
        parts.append(product.description)

    # Add category context
    if product.category:
        parts.append(f"Category: {product.category}")

    # Add tags as additional context
    if product.tags:
        tags = ", ".join(product.tags)
        parts.append(f"Related to: {tags}")

    # Fall back to name if nothing else
    if not parts:
        parts.append(product.name)

    return " ".join(parts)


def _tokenize(text: str) -> List[str]:
    return domain_keyword.tokenize(text)


def _product_tokens(product: Product) -> set[str]:
    return domain_keyword.product_tokens(
        {
            "name": product.name,
            "description": product.description,
            "tags": product.tags or [],
            "capabilities_enabled": product.capabilities_enabled or [],
            "intentionality_profile": product.intentionality_profile or {},
        }
    )


def _match_goal_to_product(goal_tokens: set[str], product: Product) -> dict:
    return domain_keyword.match_goal_to_product(
        goal_tokens,
        {
            "name": product.name,
            "description": product.description,
            "tags": product.tags or [],
            "capabilities_enabled": product.capabilities_enabled or [],
            "intentionality_profile": product.intentionality_profile or {},
        },
    )


def _missing_signals(goal: str, product: Product) -> List[str]:
    if not goal:
        return []
    goal_tokens = set(domain_keyword.tokenize(goal))
    if not goal_tokens:
        return []
    tokens = _product_tokens(product)
    return sorted(goal_tokens - tokens)


def _get_best_capability(product: Product, goal: str) -> Optional[str]:
    """Find the capability that best matches the goal."""
    return domain_keyword.best_capability(
        {"capabilities_enabled": product.capabilities_enabled or []}, goal
    )


def _average_confidence(products: List[Product]) -> float:
    """Calculate average confidence across products."""
    if not products:
        return 0.0
    return sum(product.confidence for product in products) / len(products)


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
