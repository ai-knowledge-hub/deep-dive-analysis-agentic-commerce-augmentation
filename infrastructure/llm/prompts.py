"""Infrastructure wrapper for prompt builders.

Canonical implementation currently lives in `shared.llm.prompts`.
"""

from __future__ import annotations

from shared.llm.prompts import (
    INTENT_CLASSIFICATION_PROMPT,
    VALUES_CLARIFICATION_PROMPT,
    build_optimization_prompt as _build_optimization_prompt,
)


def build_optimization_prompt(
    *,
    name: str,
    description: str,
    signals: str,
    price: float | None = None,
    tone: str | None = None,
    lessons: list[str] | None = None,
) -> str:
    return _build_optimization_prompt(
        name=name,
        description=description,
        signals=signals,
        price=price,
        tone=tone,
        lessons=lessons,
    )


__all__ = [
    "INTENT_CLASSIFICATION_PROMPT",
    "VALUES_CLARIFICATION_PROMPT",
    "build_optimization_prompt",
]
