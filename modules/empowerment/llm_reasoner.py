"""Product reasoning agent that explains empowerment alignment."""

from __future__ import annotations

from typing import List

from shared.llm.gateway import generate
from shared.llm.prompts import PRODUCT_REASONING_PROMPT


def reason_about_products(
    goals: List[str], products: List[dict], context: str | None = None
) -> List[dict]:
    """Annotate product entries with empowerment reasoning."""
    if not products:
        return []

    annotated = []
    for product in products:
        prompt = _compose_prompt(goals, product, context)
        response = generate(prompt=prompt)
        annotated.append({**product, "reasoning": response.strip()})
    return annotated


def _compose_prompt(
    goals: List[str], product: dict, session_context: str | None
) -> str:
    """Compose the prompt for product reasoning."""
    sections = [PRODUCT_REASONING_PROMPT]
    if session_context:
        sections.append(f"Session context:\n{session_context}")
    sections.append(_format_context(goals, product))
    return "\n\n".join(sections)


def _format_context(goals: List[str], product: dict) -> str:
    """Format goals and product info for the prompt."""
    goals_text = (
        "\n".join(f"- {goal}" for goal in goals) or "No explicit goals captured."
    )
    details = [
        f"Name: {product.get('name')}",
        f"Capabilities: {', '.join(product.get('capabilities_enabled', []))}",
        f"Confidence: {product.get('confidence')}",
        f"Source: {product.get('source')}",
    ]
    return f"User goals:\n{goals_text}\n\nProduct:\n" + "\n".join(details)


__all__ = ["reason_about_products"]
