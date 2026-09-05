from __future__ import annotations

from typing import Any, Dict

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    denial_event,
    mark_authorized_effect_uncertain,
)
from application.services.agent_runtime.runtime.authorized_execution import (
    AuthorizedExecutionState,
)
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


def record_approval_authorization_failure(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    error: ApprovalAuthorizationError,
    state: AuthorizedExecutionState,
) -> None:
    if state.effect_invoked:
        mark_authorized_effect_uncertain(
            deps=deps,
            run=run,
            action=action,
            authorization=state.authorization,
            error_code=error.code,
        )
    else:
        deps.agent_events.create_agent_event(
            **denial_event(
                run=run,
                action=action,
                error=error,
                phase=state.phase,
            )
        )
    _record_failed_action_and_run(
        deps=deps,
        run=run,
        action=action,
        error=str(error),
        is_policy_event=True,
        emit_action_event=False,
    )


def record_capability_failure(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    state: AuthorizedExecutionState,
    error: str,
    error_code: str,
) -> None:
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=action,
        authorization=state.authorization,
        error_code=error_code,
    )
    _record_failed_action_and_run(
        deps=deps,
        run=run,
        action=action,
        error=error,
        is_policy_event=False,
    )


def record_runtime_failure(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    error: str,
) -> None:
    _record_failed_action_and_run(
        deps=deps,
        run=run,
        action=action,
        error=error,
        is_policy_event=True,
    )


def _record_failed_action_and_run(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    error: str,
    is_policy_event: bool,
    emit_action_event: bool = True,
) -> None:
    run_id = str(run.get("id") or "")
    deps.agent_actions.update_agent_action_status(
        action_id=str(action.get("id") or ""),
        status="failed",
        outputs={},
        outputs_hash=hash_payload({}),
        error=error,
    )
    deps.agent_runs.update_agent_run(run_id=run_id, status="failed", error=error)
    if emit_action_event:
        record_action_event(
            deps=deps,
            run_id=run_id,
            action=action,
            event_type="action_failed",
            status="failed",
            note=error,
            is_policy_event=is_policy_event,
        )


__all__ = [
    "record_approval_authorization_failure",
    "record_capability_failure",
    "record_policy_failure_and_stop",
    "record_runtime_failure",
]
