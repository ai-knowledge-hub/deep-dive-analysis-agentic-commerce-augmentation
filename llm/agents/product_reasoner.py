"""Product reasoning agent that explains empowerment alignment."""

from __future__ import annotations

from typing import List

from llm.gateway import generate
from llm.prompts import PRODUCT_REASONING_PROMPT


def reason_about_products(goals: List[str], products: List[dict]) -> List[dict]:
    """Annotate product entries with empowerment reasoning."""
    if not products:
        return []

    annotated = []
    for product in products:
        context = _format_context(goals, product)
        response = generate(
            prompt=f"{PRODUCT_REASONING_PROMPT}\n\n{context}"
        )
        annotated.append({**product, "reasoning": response.strip()})
    return annotated


def _format_context(goals: List[str], product: dict) -> str:
    goals_text = "\n".join(f"- {goal}" for goal in goals) or "No explicit goals captured."
    details = [
        f"Name: {product.get('name')}",
        f"Capabilities: {', '.join(product.get('capabilities_enabled', []))}",
        f"Confidence: {product.get('confidence')}",
        f"Source: {product.get('source')}",
    ]
    return f"User goals:\n{goals_text}\n\nProduct:\n" + "\n".join(details)
