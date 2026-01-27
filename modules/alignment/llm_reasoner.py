"""Compatibility shim for product reasoning (LLM explanations).

Canonical runner lives in `infrastructure.llm.product_reasoner`.
Pure prompt composition lives in `domain.alignment.reasoning_prompt`.

Test seam preserved:
- `modules.alignment.llm_reasoner.generate`
"""

from __future__ import annotations

from typing import List

from shared.llm.gateway import generate
from shared.llm.prompts import PRODUCT_REASONING_PROMPT
from infrastructure.llm.product_reasoner import reason_about_products as _reason_about_products


def reason_about_products(
    goals: List[str], products: List[dict], context: str | None = None
) -> List[dict]:
    """Annotate product entries with alignment reasoning."""
    return _reason_about_products(
        goals,
        products,
        context=context,
        generate_fn=generate,
        prompt_template=PRODUCT_REASONING_PROMPT,
    )


__all__ = ["reason_about_products"]
