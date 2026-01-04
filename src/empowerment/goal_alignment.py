"""AIS-inspired goal alignment scoring."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from src.products.schemas import Product

@dataclass
class GoalAlignmentResult:
    score: float
    aligned_goals: List[str]
    misaligned_goals: List[str]
    supporting_products: List[str]


def assess(goals: List[str], products: List[Product]) -> GoalAlignmentResult:
    aligned: List[str] = []
    supporting_products: List[str] = []
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
    misaligned = [goal for goal in goals if goal not in aligned]
    score = len(aligned) / max(len(goals), 1)
    return GoalAlignmentResult(
        score=score,
        aligned_goals=aligned,
        misaligned_goals=misaligned,
        supporting_products=supporting_products,
    )
