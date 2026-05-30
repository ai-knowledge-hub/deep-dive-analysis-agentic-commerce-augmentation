from __future__ import annotations

from typing import Any, Dict, List

from application.services.agent_runtime.registry.catalog import get_capability_spec


def apply_planner_mode(
    *,
    actions: List[Any],
    planner_mode: str | None,
    objective: Dict[str, Any],
) -> List[Any]:
    mode = str(planner_mode or "").strip()
    shaped = list(actions)
    if mode == "inspect_and_recommend":
        shaped = [
            action
            for action in shaped
            if _effect_class(action.capability_name) in {"read", "recommend"}
        ]
    if mode == "bounded_single_or_workflow":
        if str(objective.get("plan_mode") or "").strip().lower() == "single_tool":
            shaped = shaped[:1]
        else:
            shaped = shaped[: _max_initial_actions(objective)]
    return shaped


def _effect_class(capability_name: str) -> str:
    spec = get_capability_spec(capability_name)
    return str(getattr(spec, "effect_class", "") or "")


def _max_initial_actions(objective: Dict[str, Any]) -> int:
    try:
        parsed = int(objective.get("max_initial_actions") or 50)
    except (TypeError, ValueError):
        return 50
    return max(1, min(parsed, 50))


__all__ = ["apply_planner_mode"]
