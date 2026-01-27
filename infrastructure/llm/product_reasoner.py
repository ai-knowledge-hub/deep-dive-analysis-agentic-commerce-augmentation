"""Infrastructure runner for per-product reasoning (LLM calls)."""

from __future__ import annotations

from typing import Callable, List

from domain.alignment.reasoning_prompt import compose_reasoning_prompt


GenerateFn = Callable[..., str]


def reason_about_products(
    goals: List[str],
    products: List[dict],
    *,
    context: str | None = None,
    generate_fn: GenerateFn,
    prompt_template: str,
) -> List[dict]:
    if not products:
        return []

    annotated: List[dict] = []
    for product in products:
        prompt = compose_reasoning_prompt(
            template=prompt_template,
            goals=goals,
            product=product,
            session_context=context,
        )
        response = generate_fn(prompt=prompt)
        annotated.append({**product, "reasoning": (response or "").strip()})
    return annotated


__all__ = ["reason_about_products", "GenerateFn"]

