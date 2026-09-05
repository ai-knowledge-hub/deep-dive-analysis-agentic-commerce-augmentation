from __future__ import annotations

from typing import Any, Dict

from application.ports.deps import AppDeps
from application.services.agent_runtime.registry import get_harness_profile
from application.services.agent_runtime.runtime.audit import record_run_event
from application.services.agent_runtime.runtime.stopping import (
    StopDecision,
    evaluate_stopping_conditions,
)


def apply_stopping_condition(
    *, deps: AppDeps, run: Dict[str, Any]
) -> StopDecision | None:
    run_id = str(run.get("id") or "")
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=500)
    stop = evaluate_stopping_conditions(run=run, actions=actions)
    if not stop:
        return None
    deps.agent_runs.update_agent_run(run_id=run_id, status=stop.status, error=None)
    _record_stop(deps=deps, run_id=run_id, stop=stop)
    return stop


def record_operator_pause_condition(*, deps: AppDeps, run: Dict[str, Any]) -> None:
    harness = get_harness_profile(str(run.get("harness_id") or "")) or {}
    conditions = {
        str(item).strip()
        for item in list(harness.get("stopping_conditions") or [])
        if str(item).strip()
    }
    if "operator_pause" in conditions:
        _record_stop(
            deps=deps,
            run_id=str(run.get("id") or ""),
            stop=StopDecision(
                status="paused",
                condition="operator_pause",
                note="Run paused by operator.",
            ),
        )


def compute_next_run_status(*, deps: AppDeps, run: Dict[str, Any], run_id: str) -> str:
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=500)
    status, stop = derive_next_run_status(run=run, actions=actions)
    if stop:
        record_stopping_decision(deps=deps, run_id=run_id, stop=stop)
    return status


def derive_next_run_status(
    *, run: Dict[str, Any], actions: list[Dict[str, Any]]
) -> tuple[str, StopDecision | None]:
    """Derive status from one caller-owned action snapshot without side effects."""

    stop = evaluate_stopping_conditions(run=run, actions=actions)
    if stop:
        return stop.status, stop
    statuses = {str(item.get("status") or "").lower() for item in actions}
    if "failed" in statuses:
        return "failed", None
    if "approved" in statuses or "executing" in statuses:
        return "running", None
    if "proposed" in statuses:
        return "planned", None
    if statuses and statuses.issubset({"executed", "rejected"}):
        return "completed", None
    return "planned", None


def record_stopping_decision(*, deps: AppDeps, run_id: str, stop: StopDecision) -> None:
    _record_stop(deps=deps, run_id=run_id, stop=stop)


def _record_stop(*, deps: AppDeps, run_id: str, stop: StopDecision) -> None:
    record_run_event(
        deps=deps,
        run_id=run_id,
        sequence=0,
        event_type="run_stopping_condition_met",
        status=stop.status,
        note=stop.note,
        anchors={"stopping_condition": stop.condition},
    )


__all__ = [
    "apply_stopping_condition",
    "compute_next_run_status",
    "derive_next_run_status",
    "record_operator_pause_condition",
    "record_stopping_decision",
]
