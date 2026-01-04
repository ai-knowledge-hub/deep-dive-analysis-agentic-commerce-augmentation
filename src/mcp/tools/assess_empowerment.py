"""MCP tool for empowerment metrics."""

from __future__ import annotations

from typing import List

from src.empowerment.goal_alignment import assess
from src.memory.semantic import SemanticMemory
from src.products.search import search


def run(product_ids: List[str]) -> dict:
    memory = SemanticMemory()
    goals = memory.get("goals")
    products = [product for product in search("") if product.id in product_ids]
    result = assess(goals, products)
    return {
        "score": result.score,
        "aligned_goals": result.aligned_goals,
        "misaligned_goals": result.misaligned_goals,
        "supporting_products": result.supporting_products,
    }
