"""MCP tool for empowerment metrics."""

from __future__ import annotations

from typing import List

from modules.empowerment.goal_alignment import assess
from modules.memory.semantic import SemanticMemory
from modules.commerce.search import search


def run(goals: List[str], product_ids: List[str]) -> dict:
    """Evaluate alignment between stored goals and provided products."""
    memory = SemanticMemory()
    stored_goals = memory.get("goals")
    combined_goals = list(dict.fromkeys((stored_goals or []) + (goals or [])))

    catalog = search("")
    id_to_product = {product.id: product for product in catalog}
    selected_products = [
        id_to_product[_id] for _id in product_ids if _id in id_to_product
    ]

    assessment = assess(combined_goals or stored_goals or goals, selected_products)
    return {
        "score": assessment.score,
        "aligned_goals": assessment.aligned_goals,
        "misaligned_goals": assessment.misaligned_goals,
        "supporting_products": assessment.supporting_products,
        "confidence_summary": assessment.confidence_summary,
    }


__all__ = ["run"]
