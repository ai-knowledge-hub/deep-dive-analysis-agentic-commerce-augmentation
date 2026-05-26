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
    if "budget_exhausted" in conditions and _budget_exhausted(run=run, actions=actions):
        return StopDecision(
            status="paused",
            condition="budget_exhausted",
            note="Run paused because a harness budget is exhausted.",
        )
    if "policy_block" in conditions and _has_policy_blocked_action(actions):
        return StopDecision(
            status="paused",
            condition="policy_block",
            note="Run paused because policy blocked an action.",
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
    if (
        "all_actions_decided" in conditions
        and statuses
        and statuses.issubset({"approved", "executed", "rejected"})
    ):
        return StopDecision(
            status="completed",
            condition="all_actions_decided",
            note="Run completed because all actions were approved or rejected.",
        )
    return None


def _budget_exhausted(*, run: Dict[str, Any], actions: List[Dict[str, Any]]) -> bool:
    budgets = dict(run.get("budgets") or {})
    max_actions = _safe_int(budgets.get("max_actions"))
    executed = [
        item for item in actions if str(item.get("status") or "").lower() == "executed"
    ]
    if max_actions is not None and len(executed) >= max_actions:
        return True
    max_variant_runs = _safe_int(budgets.get("max_variant_runs"))
    if max_variant_runs is not None:
        variant_runs = [
            item
            for item in executed
            if str(item.get("capability_name") or "") == "run_variant"
        ]
        if len(variant_runs) >= max_variant_runs:
            return True
    max_cost_usd = _safe_float(budgets.get("max_cost_usd"))
    return max_cost_usd is not None and _consumed_cost_usd(executed) >= max_cost_usd


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


def _has_policy_blocked_action(actions: List[Dict[str, Any]]) -> bool:
    for action in actions:
        status = str(action.get("status") or "").lower()
        if status != "failed":
            continue
        error = str(action.get("error") or "").strip().lower()
        if not error:
            continue
        if (
            "policy profile" in error
            or "capability '" in error
            or "budget exceeded" in error
            or "missing required inputs" in error
        ):
            return True
    return False


def _safe_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _consumed_cost_usd(actions: List[Dict[str, Any]]) -> float:
    cost_keys = {"cost_usd", "total_cost_usd", "validation_cost_usd", "estimated_cost_usd"}
    return sum(_sum_numeric_fields(action.get("outputs") or {}, cost_keys) for action in actions)


def _sum_numeric_fields(value: Any, keys: set[str]) -> float:
    if isinstance(value, list):
        return sum(_sum_numeric_fields(item, keys) for item in value)
    if not isinstance(value, dict):
        return 0.0
    total = 0.0
    for key, nested in value.items():
        if key in keys:
            number = _safe_float(nested)
            if number is not None:
                total += number
        total += _sum_numeric_fields(nested, keys)
    return total


__all__ = ["StopDecision", "evaluate_stopping_conditions"]
