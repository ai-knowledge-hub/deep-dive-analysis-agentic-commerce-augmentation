from __future__ import annotations

from typing import Any, Dict

from application.ports.deps import AppDeps
from application.services.agent_runtime.runtime.audit import record_action_event
from application.services.agent_runtime.runtime.payloads import hash_payload
from application.services.agent_runtime.runtime.status import apply_stopping_condition
from application.services.agent_runtime.runtime.stopping import StopDecision


def record_policy_failure_and_stop(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    error: str,
) -> StopDecision | None:
    run_id = str(run.get("id") or "")
    deps.agent_actions.update_agent_action_status(
        action_id=str(action.get("id") or ""),
        status="failed",
        outputs={},
        outputs_hash=hash_payload({}),
        error=error,
    )
    record_action_event(
        deps=deps,
        run_id=run_id,
        action=action,
        event_type="action_failed",
        status="failed",
        note=error,
        is_policy_event=True,
    )
    return apply_stopping_condition(deps=deps, run=run)


__all__ = ["record_policy_failure_and_stop"]
