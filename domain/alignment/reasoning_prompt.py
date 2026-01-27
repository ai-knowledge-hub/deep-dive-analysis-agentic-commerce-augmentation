"""Pure prompt composition for per-product reasoning."""

from __future__ import annotations

from typing import List


def format_reasoning_context(goals: List[str], product: dict) -> str:
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


def compose_reasoning_prompt(
    *,
    template: str,
    goals: List[str],
    product: dict,
    session_context: str | None,
) -> str:
    sections = [template]
    if session_context:
        sections.append(f"Session context:\n{session_context}")
    sections.append(format_reasoning_context(goals, product))
    return "\n\n".join(sections)


__all__ = ["compose_reasoning_prompt", "format_reasoning_context"]
