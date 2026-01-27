from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence


def _stable_dedupe(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_intent_goals(
    intent: Mapping[str, Any] | None,
    *,
    explicit_goals: Sequence[str] | None = None,
    fallback: str | None = None,
) -> list[str]:
    """Merge explicit goals + inferred intent fields into a stable, deduped list.

    Pure helper used across conversation + simulation.
    """
    merged: list[str] = []
    if explicit_goals:
        merged.extend([goal for goal in explicit_goals if goal])

    intent = intent or {}
    primary = intent.get("primary_goal") or intent.get("label")
    if primary and primary != "unknown":
        merged.append(str(primary))

    secondary = intent.get("secondary_goals") or []
    if isinstance(secondary, Sequence):
        merged.extend([str(goal) for goal in secondary if goal and goal != "unknown"])

    needs = intent.get("underlying_needs") or []
    if isinstance(needs, Sequence):
        merged.extend([str(goal) for goal in needs if goal and goal != "unknown"])

    merged = [goal for goal in merged if goal and goal != "unknown"]
    deduped = _stable_dedupe(merged)
    if not deduped and fallback:
        deduped = [fallback]
    return deduped


__all__ = ["extract_intent_goals"]
