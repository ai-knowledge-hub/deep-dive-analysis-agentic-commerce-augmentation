"""Infrastructure adapter for alignment scoring.

This binds the pure scoring functions in `domain.alignment.scoring` to the
current embedding provider in `shared.llm.embeddings`.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any, List, Mapping

from domain.alignment import scoring as domain_scoring
from domain.alignment import keyword as domain_keyword
from domain.alignment.types import AlignmentScore, AlignmentSummary
from infrastructure.llm import embeddings as embeddings_provider
from shared.llm.embeddings import cosine_similarity, get_embedding_provider

logger = logging.getLogger(__name__)

HIGH_ALIGNMENT_THRESHOLD = 0.7
MEDIUM_ALIGNMENT_THRESHOLD = 0.5


def _as_mapping(item: Any) -> Mapping[str, Any]:
    if isinstance(item, Mapping):
        return item
    if is_dataclass(item):
        return asdict(item)
    if hasattr(item, "__dict__"):
        return dict(getattr(item, "__dict__"))
    return {"value": item}


def _embedding_provider_name() -> str:
    try:
        provider = get_embedding_provider()
    except Exception:
        return "unknown"

    # Accessing some provider properties can trigger lazy initialization and raise
    # if no provider is available; keep this best-effort and never fail scoring.
    for attr in ("provider_name", "name"):
        try:
            value = getattr(provider, attr)
        except Exception:
            continue
        if isinstance(value, str) and value:
            return value

    return provider.__class__.__name__


def assess(
    goals: List[str], products: List[Any], *, use_semantic: bool = True
) -> AlignmentSummary:
    """Assess overall alignment summary for a set of candidate products."""
    product_maps = [_as_mapping(p) for p in (products or [])]

    if use_semantic:
        try:
            goal_texts = [str(g) for g in goals]
            product_texts = [
                domain_scoring.build_product_semantic_text(p) for p in product_maps
            ]
            all_texts = goal_texts + product_texts
            embeddings = embeddings_provider.embed_batch(all_texts)
            goal_embeddings = embeddings[: len(goal_texts)]
            product_embeddings = embeddings[len(goal_texts) :]
            return domain_scoring.semantic_assess(
                goals=goal_texts,
                products=product_maps,
                goal_embeddings=goal_embeddings,
                product_embeddings=product_embeddings,
                cosine_similarity=cosine_similarity,
                provider_name=_embedding_provider_name(),
                high_threshold=HIGH_ALIGNMENT_THRESHOLD,
                medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
            )
        except Exception as exc:
            if embeddings_provider.embedding_available():
                logger.warning(
                    "Semantic per-product scoring failed, falling back: %s", exc
                )
            else:
                logger.debug(
                    "Semantic per-product scoring unavailable, falling back: %s", exc
                )

    return domain_scoring.keyword_assess(
        goals=goals,
        products=product_maps,
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


def score_products(
    goals: List[str], products: List[Any], *, use_semantic: bool = True
) -> List[AlignmentScore]:
    """Return per-product alignment scores with explanations."""
    product_maps = [_as_mapping(p) for p in (products or [])]

    if use_semantic:
        try:
            goal_texts = [str(g) for g in goals]
            product_texts = [
                domain_scoring.build_product_semantic_text(p) for p in product_maps
            ]
            all_texts = goal_texts + product_texts
            embeddings = embeddings_provider.embed_batch(all_texts)
            goal_embeddings = embeddings[: len(goal_texts)]
            product_embeddings = embeddings[len(goal_texts) :]
            return domain_scoring.semantic_score_products(
                goals=goal_texts,
                products=product_maps,
                goal_embeddings=goal_embeddings,
                product_embeddings=product_embeddings,
                cosine_similarity=cosine_similarity,
                high_threshold=HIGH_ALIGNMENT_THRESHOLD,
                medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
            )
        except Exception as exc:
            if embeddings_provider.embedding_available():
                logger.warning(
                    "Semantic per-product scoring failed, falling back: %s", exc
                )
            else:
                logger.debug(
                    "Semantic per-product scoring unavailable, falling back: %s", exc
                )

    return domain_scoring.keyword_score_products(
        goals=goals,
        products=product_maps,
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


def get_alignment_explanation(goal: str, product: Any, similarity_score: float) -> str:
    """Compatibility helper used by older tests and UI pieces."""
    product_map = dict(_as_mapping(product))
    missing = domain_scoring._missing_signals(goal, product_map)  # type: ignore[attr-defined]
    return domain_keyword.alignment_explanation(
        goal=goal,
        similarity_score=float(similarity_score),
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
        capabilities_enabled=product_map.get("capabilities_enabled") or [],
        matched_caps=None,
        missing_signals=missing,
    )


def _build_product_semantic_text(product: Any) -> str:
    return domain_scoring.build_product_semantic_text(dict(_as_mapping(product)))


def _keyword_assess(goals: List[str], products: List[Any]) -> AlignmentSummary:
    product_maps = [_as_mapping(p) for p in (products or [])]
    return domain_scoring.keyword_assess(
        goals=goals,
        products=product_maps,
        high_threshold=HIGH_ALIGNMENT_THRESHOLD,
        medium_threshold=MEDIUM_ALIGNMENT_THRESHOLD,
    )


__all__ = [
    "assess",
    "score_products",
    "HIGH_ALIGNMENT_THRESHOLD",
    "MEDIUM_ALIGNMENT_THRESHOLD",
    "get_alignment_explanation",
    "_build_product_semantic_text",
    "_keyword_assess",
]
