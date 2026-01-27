"""Pure alignment scoring functions.

This module is intentionally dependency-free:
- no DB access
- no embedding providers
- no network/LLM calls

Callers provide embeddings and similarity functions.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence

from domain.alignment import keyword as kw
from domain.alignment.types import AlignmentScore, AlignmentSummary


def build_product_semantic_text(product: Mapping[str, Any]) -> str:
    parts: List[str] = []

    capabilities = product.get("capabilities_enabled") or []
    if capabilities:
        parts.append(
            f"This product enables: {', '.join([str(c) for c in capabilities])}"
        )

    description = product.get("description") or ""
    if description:
        parts.append(str(description))

    category = product.get("category") or ""
    if category:
        parts.append(f"Category: {category}")

    tags = product.get("tags") or []
    if tags:
        parts.append(f"Related to: {', '.join([str(t) for t in tags])}")

    if not parts:
        parts.append(str(product.get("name") or ""))

    return " ".join([p for p in parts if p]).strip()


def keyword_assess(
    *,
    goals: Sequence[str],
    products: Sequence[Mapping[str, Any]],
    high_threshold: float,
    medium_threshold: float,
) -> AlignmentSummary:
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
            misaligned_goals=list(goals),
            supporting_products=[],
            confidence_summary={
                "average_confidence": 0.0,
                "aligned_goal_confidence": {},
            },
        )

    aligned: List[str] = []
    supporting_products: List[str] = []
    goal_confidence: Dict[str, float] = {}

    for goal in goals:
        goal_tokens = set(kw.tokenize(goal))
        if not goal_tokens:
            continue

        goal_products: List[Mapping[str, Any]] = []
        for product in products:
            match = kw.match_goal_to_product(goal_tokens, dict(product))
            if match["score"] >= medium_threshold:
                goal_products.append(product)
                supporting_products.append(
                    str(product.get("id") or product.get("product_id") or "")
                )

        if goal_products:
            aligned.append(goal)
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
        "aligned_goal_confidence": {g: round(s, 2) for g, s in goal_confidence.items()},
        "alignment_method": "keyword",
    }

    return AlignmentSummary(
        score=weighted_score,
        aligned_goals=aligned,
        misaligned_goals=misaligned,
        supporting_products=kw.dedupe_keep_order([p for p in supporting_products if p]),
        confidence_summary=confidence_summary,
    )


def semantic_assess(
    *,
    goals: Sequence[str],
    products: Sequence[Mapping[str, Any]],
    goal_embeddings: Sequence[Sequence[float]],
    product_embeddings: Sequence[Sequence[float]],
    cosine_similarity: Callable[[Sequence[float], Sequence[float]], float],
    provider_name: str,
    high_threshold: float,
    medium_threshold: float,
) -> AlignmentSummary:
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
            misaligned_goals=list(goals),
            supporting_products=[],
            confidence_summary={
                "average_confidence": 0.0,
                "aligned_goal_confidence": {},
            },
        )

    aligned_goals: List[str] = []
    misaligned_goals: List[str] = []
    supporting_products: List[str] = []
    goal_confidence: Dict[str, float] = {}

    id_for_product = [_product_id(p) for p in products]

    for j, goal in enumerate(goals):
        goal_emb = goal_embeddings[j]
        max_similarity = 0.0
        supporting_ids: List[str] = []

        for i, product_emb in enumerate(product_embeddings):
            similarity = cosine_similarity(goal_emb, product_emb)
            if similarity >= medium_threshold:
                supporting_ids.append(id_for_product[i])
                max_similarity = max(max_similarity, similarity)

        if supporting_ids:
            aligned_goals.append(goal)
            supporting_products.extend(supporting_ids)
            avg_conf = _average_confidence(
                [p for p, pid in zip(products, id_for_product) if pid in supporting_ids]
            )
            goal_confidence[goal] = max_similarity * avg_conf
        else:
            misaligned_goals.append(goal)

    supporting_products = kw.dedupe_keep_order([p for p in supporting_products if p])

    base_score = len(aligned_goals) / len(goals) if goals else 0.0
    confidence_weight = (
        sum(goal_confidence.values()) / max(len(goal_confidence), 1)
        if goal_confidence
        else 0.0
    )
    weighted_score = round(base_score * (0.6 + 0.4 * confidence_weight), 3)

    confidence_summary: Dict[str, float | Dict[str, float]] = {
        "average_confidence": round(_average_confidence(products), 2),
        "aligned_goal_confidence": {g: round(s, 3) for g, s in goal_confidence.items()},
        "embedding_provider": provider_name,
        "alignment_method": "semantic",
    }

    return AlignmentSummary(
        score=weighted_score,
        aligned_goals=aligned_goals,
        misaligned_goals=misaligned_goals,
        supporting_products=supporting_products,
        confidence_summary=confidence_summary,
    )


def keyword_score_products(
    *,
    goals: Sequence[str],
    products: Sequence[Mapping[str, Any]],
    high_threshold: float,
    medium_threshold: float,
) -> List[AlignmentScore]:
    if not goals or not products:
        return []

    scores: List[AlignmentScore] = []
    for product in products:
        best_goal: Optional[str] = None
        best_score = 0.0
        best_match: Dict[str, Any] = {"capabilities": [], "missing": []}

        for goal in goals:
            goal_tokens = set(kw.tokenize(goal))
            if not goal_tokens:
                continue
            match = kw.match_goal_to_product(goal_tokens, dict(product))
            if match["score"] > best_score:
                best_score = float(match["score"])
                best_goal = goal
                best_match = match

        matched_caps: List[str] = list(best_match.get("capabilities") or [])
        best_cap = kw.best_capability(dict(product), best_goal or "")
        if not matched_caps and best_cap:
            matched_caps = [best_cap]

        reasoning = kw.alignment_explanation(
            goal=best_goal or "",
            similarity_score=best_score,
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            capabilities_enabled=product.get("capabilities_enabled") or [],
            matched_caps=matched_caps,
            missing_signals=best_match.get("missing") or [],
        )

        scores.append(
            AlignmentScore(
                product_id=_product_id(product),
                score=round(best_score, 3),
                matched_capabilities=kw.dedupe_keep_order(matched_caps),
                alignment_reasoning=reasoning,
                confidence=round(float(product.get("confidence") or 0.0), 2),
                low_confidence=best_score < medium_threshold,
            )
        )

    return scores


def semantic_score_products(
    *,
    goals: Sequence[str],
    products: Sequence[Mapping[str, Any]],
    goal_embeddings: Sequence[Sequence[float]],
    product_embeddings: Sequence[Sequence[float]],
    cosine_similarity: Callable[[Sequence[float], Sequence[float]], float],
    high_threshold: float,
    medium_threshold: float,
) -> List[AlignmentScore]:
    if not goals or not products:
        return []

    scores: List[AlignmentScore] = []
    for product, product_emb in zip(products, product_embeddings):
        best_score = 0.0
        best_goal: Optional[str] = None

        for goal, goal_emb in zip(goals, goal_embeddings):
            similarity = cosine_similarity(goal_emb, product_emb)
            if similarity > best_score:
                best_score = float(similarity)
                best_goal = goal

        best_cap = kw.best_capability(dict(product), best_goal or "")
        missing = _missing_signals(best_goal or "", product)

        reasoning = kw.alignment_explanation(
            goal=best_goal or "",
            similarity_score=best_score,
            high_threshold=high_threshold,
            medium_threshold=medium_threshold,
            capabilities_enabled=product.get("capabilities_enabled") or [],
            matched_caps=[best_cap] if best_cap else [],
            missing_signals=missing,
        )

        scores.append(
            AlignmentScore(
                product_id=_product_id(product),
                score=round(best_score, 3),
                matched_capabilities=[c for c in [best_cap] if c],
                alignment_reasoning=reasoning,
                confidence=round(float(product.get("confidence") or 0.0), 2),
                low_confidence=best_score < medium_threshold,
            )
        )

    return scores


def _product_id(product: Mapping[str, Any]) -> str:
    return str(product.get("id") or product.get("product_id") or "")


def _average_confidence(products: Sequence[Mapping[str, Any]]) -> float:
    if not products:
        return 0.0
    total = 0.0
    count = 0
    for product in products:
        try:
            total += float(product.get("confidence") or 0.0)
        except (TypeError, ValueError):
            total += 0.0
        count += 1
    return total / max(count, 1)


def _missing_signals(goal: str, product: Mapping[str, Any]) -> List[str]:
    if not goal:
        return []
    goal_tokens = set(kw.tokenize(goal))
    if not goal_tokens:
        return []
    tokens = kw.product_tokens(dict(product))
    return sorted(goal_tokens - tokens)


__all__ = [
    "AlignmentScore",
    "AlignmentSummary",
    "build_product_semantic_text",
    "keyword_assess",
    "semantic_assess",
    "keyword_score_products",
    "semantic_score_products",
]
