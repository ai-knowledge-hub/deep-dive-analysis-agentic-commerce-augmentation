"""AIS-inspired goal alignment scoring with confidence weighting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from src.products.schemas import Product


@dataclass
class GoalAlignmentResult:
    score: float
    aligned_goals: List[str]
    misaligned_goals: List[str]
    supporting_products: List[str]
    confidence_summary: Dict[str, float | Dict[str, float]]


def assess(goals: List[str], products: List[Product]) -> GoalAlignmentResult:
    aligned: List[str] = []
    supporting_products: List[str] = []
    goal_confidence: Dict[str, float] = {}

    for goal in goals:
        normalized = goal.lower()
        goal_tokens = set(normalized.split())
        goal_products = [
            product
            for product in products
            if any(goal_tokens & set(capability.lower().split()) for capability in product.capabilities_enabled)
            or any(tag in normalized or normalized in tag for tag in product.tags)
        ]
        if goal_products:
            aligned.append(goal)
            supporting_products.extend(product.id for product in goal_products)
            goal_confidence[goal] = _average_confidence(goal_products)

    misaligned = [goal for goal in goals if goal not in aligned]
    base_score = len(aligned) / max(len(goals), 1)
    confidence_weight = (
        sum(goal_confidence.values()) / max(len(goal_confidence), 1) if goal_confidence else 0.0
    )
    weighted_score = round(base_score * (0.7 + 0.3 * confidence_weight), 3)
    confidence_summary: Dict[str, float | Dict[str, float]] = {
        "average_confidence": round(_average_confidence(products), 2) if products else 0.0,
        "aligned_goal_confidence": {goal: round(score, 2) for goal, score in goal_confidence.items()},
    }

    return GoalAlignmentResult(
        score=weighted_score,
        aligned_goals=aligned,
        misaligned_goals=misaligned,
        supporting_products=supporting_products,
        confidence_summary=confidence_summary,
    )


def _average_confidence(products: List[Product]) -> float:
    if not products:
        return 0.0
    return sum(product.confidence for product in products) / len(products)
