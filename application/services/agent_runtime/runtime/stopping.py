from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from application.services.agent_runtime.registry import get_capability_spec, get_harness_profile


@dataclass(frozen=True)
class StopDecision:
    status: str
    condition: str
    note: str


def evaluate_stopping_conditions(
    *, run: Dict[str, Any], actions: List[Dict[str, Any]]
) -> StopDecision | None:
    harness = get_harness_profile(str(run.get("harness_id") or "")) or {}
    conditions = {
        str(item).strip()
        for item in list(harness.get("stopping_conditions") or [])
        if str(item).strip()
    }
    if not conditions:
        return None
    statuses = {str(item.get("status") or "").lower() for item in actions}
    if "external_side_effect_required" in conditions and _has_pending_external_effect(
        actions
    ):
        return StopDecision(
            status="paused",
            condition="external_side_effect_required",
            note="Run paused before external side-effect capability required by harness.",
        )
    if "recommendation_produced" in conditions and any(
        str(item.get("capability_name") or "") == "recommend_next_action"
        and str(item.get("status") or "").lower() == "executed"
        for item in actions
    ):
        return StopDecision(
            status="completed",
            condition="recommendation_produced",
            note="Run completed because the harness recommendation was produced.",
        )
    if (
        "all_actions_completed" in conditions
        and statuses
        and statuses.issubset({"executed", "rejected"})
    ):
        return StopDecision(
            status="completed",
            condition="all_actions_completed",
            note="Run completed because all actions reached terminal decisions.",
        )
    return None


def _has_pending_external_effect(actions: List[Dict[str, Any]]) -> bool:
    for action in actions:
        status = str(action.get("status") or "").lower()
        if status not in {"approved", "executing", "proposed"}:
            continue
        spec = get_capability_spec(str(action.get("capability_name") or ""))
        effect_class = str(getattr(spec, "effect_class", "") or "")
        if effect_class in {"external_side_effect", "write_high_risk"}:
            return True
    return False


__all__ = ["StopDecision", "evaluate_stopping_conditions"]
