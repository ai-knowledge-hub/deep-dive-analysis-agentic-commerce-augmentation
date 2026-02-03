from __future__ import annotations

from typing import Any, Dict, Optional


def judge_pairwise(
    *,
    query: str,
    product_a: Dict[str, Any],
    product_b: Dict[str, Any],
    generate_fn,
    provider: Optional[str] = None,
) -> Dict[str, Any]:
    prompt = _build_prompt(query=query, product_a=product_a, product_b=product_b)
    response = generate_fn(
        prompt, provider=provider, system_instruction=_system_instruction()
    )
    decision = _parse_winner(response)
    return {
        "provider": provider or "default",
        "winner": decision,
        "raw": response,
    }


def _system_instruction() -> str:
    return "You are a shopping intent judge. Choose the product that best matches the query."


def _build_prompt(
    *, query: str, product_a: Dict[str, Any], product_b: Dict[str, Any]
) -> str:
    return (
        "USER QUERY:\n"
        f"{query}\n\n"
        "PRODUCT A:\n"
        f"Name: {product_a.get('name')}\n"
        f"Description: {product_a.get('description')}\n\n"
        "PRODUCT B:\n"
        f"Name: {product_b.get('name')}\n"
        f"Description: {product_b.get('description')}\n\n"
        "Which product is more aligned with the query? "
        "Reply with exactly one token: A, B, or TIE."
    )


def _parse_winner(response: str) -> str:
    text = (response or "").strip().lower()
    if not text:
        return "tie"
    if "a" == text or text.startswith("a"):
        return "a"
    if "b" == text or text.startswith("b"):
        return "b"
    if "tie" in text:
        return "tie"
    # fallback: check for explicit A/B in first line
    first = text.splitlines()[0].strip()
    if first.startswith("a"):
        return "a"
    if first.startswith("b"):
        return "b"
    return "tie"


__all__ = ["judge_pairwise"]
