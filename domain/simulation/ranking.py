from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Sequence


def rank_scores(scores: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return scores sorted by best score first (stable tie-breaker on product_id)."""
    return [dict(item) for item in sort_scores(scores)]


def sort_scores(scores: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    return sorted(
        scores,
        key=lambda item: (
            -(float(item.get("score") or 0.0)),
            str(item.get("product_id") or ""),
        ),
    )


def winner_id(scores: Sequence[Mapping[str, Any]]) -> Optional[str]:
    ranked = sort_scores(scores)
    if not ranked:
        return None
    return ranked[0].get("product_id")  # type: ignore[return-value]


def score_for_product(
    scores: Sequence[Mapping[str, Any]], product_id: str
) -> Optional[float]:
    for item in scores:
        if item.get("product_id") == product_id:
            try:
                return float(item.get("score"))
            except (TypeError, ValueError):
                return None
    return None


def delta_points(
    before_scores: Sequence[Mapping[str, Any]],
    after_scores: Sequence[Mapping[str, Any]],
    *,
    product_id: str,
) -> Optional[float]:
    before = score_for_product(before_scores, product_id)
    after = score_for_product(after_scores, product_id)
    if before is None or after is None:
        return None
    return (after - before) * 100.0


def lift_summary(
    *,
    before_scores: Sequence[Mapping[str, Any]] | None,
    after_scores: Sequence[Mapping[str, Any]] | None,
    optimized_product_id: str | None = None,
) -> dict[str, Any]:
    before_scores = list(before_scores or [])
    after_scores = list(after_scores or [])
    summary: dict[str, Any] = {
        "winner_before": winner_id(before_scores),
        "winner_after": winner_id(after_scores),
    }
    if optimized_product_id:
        delta = delta_points(
            before_scores, after_scores, product_id=optimized_product_id
        )
        summary.update(
            {
                "optimized_product_id": optimized_product_id,
                "score_before": score_for_product(before_scores, optimized_product_id),
                "score_after": score_for_product(after_scores, optimized_product_id),
                "delta_points": delta,
            }
        )
    return summary


def stable_dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


__all__ = [
    "rank_scores",
    "sort_scores",
    "winner_id",
    "score_for_product",
    "delta_points",
    "lift_summary",
    "stable_dedupe",
]
