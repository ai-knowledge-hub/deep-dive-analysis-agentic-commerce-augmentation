from __future__ import annotations

from typing import Any, Dict

from application.ports.deps import AppDeps
from application.services.agent_runtime.runtime.audit import record_run_event
from application.services.agent_runtime.runtime.stopping import (
    StopDecision,
    evaluate_stopping_conditions,
)


def apply_stopping_condition(*, deps: AppDeps, run: Dict[str, Any]) -> StopDecision | None:
    run_id = str(run.get("id") or "")
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=500)
    stop = evaluate_stopping_conditions(run=run, actions=actions)
    if not stop:
        return None
    deps.agent_runs.update_agent_run(run_id=run_id, status=stop.status, error=None)
    _record_stop(deps=deps, run_id=run_id, stop=stop)
    return stop


def compute_next_run_status(*, deps: AppDeps, run: Dict[str, Any], run_id: str) -> str:
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=500)
    stop = evaluate_stopping_conditions(run=run, actions=actions)
    if stop:
        _record_stop(deps=deps, run_id=run_id, stop=stop)
        return stop.status
    statuses = {str(item.get("status") or "").lower() for item in actions}
    if "failed" in statuses:
        return "failed"
    if "approved" in statuses or "executing" in statuses:
        return "running"
    if "proposed" in statuses:
        return "planned"
    if statuses and statuses.issubset({"executed", "rejected"}):
        return "completed"
    return "planned"


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


__all__ = ["apply_stopping_condition", "compute_next_run_status"]
