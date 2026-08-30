from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    validate_exact_action_approval,
)
from application.services.agent_runtime.runtime.authorized_execution import (
    AuthorizedExecutionState,
    execute_with_exact_authorization,
)
from application.services.agent_runtime.runtime.audit import (
    record_action_event,
    record_run_event,
)
from application.services.agent_runtime.runtime.failures import (
    record_approval_authorization_failure,
    record_capability_failure,
    record_policy_failure_and_stop,
    record_runtime_failure,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from application.services.agent_runtime.runtime.status import (
    apply_stopping_condition,
    compute_next_run_status,
    record_operator_pause_condition,
)
from application.services.agent_runtime.harness_posture import (
    HarnessPostureError,
    validate_harness_memory_policy,
)
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import (
    get_capability_spec,
    get_harness_profile,
    next_state_for_capability,
    run_mode_supported,
)


class AgentRuntimeError(ValueError):
    pass


class RunNotFoundError(AgentRuntimeError):
    pass


class PlanOnlyModeError(AgentRuntimeError):
    pass


class RunBusyError(AgentRuntimeError):
    pass


class NoApprovedActionError(AgentRuntimeError):
    pass


_TERMINAL_STATUSES = {"canceled", "cancelled", "completed", "failed"}
_NON_EXECUTABLE_STATUSES = {*_TERMINAL_STATUSES, "paused"}


@dataclass(frozen=True)
class RuntimeResult:
    run: Dict[str, Any]
    action: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


class AgentRuntimeService:
    def __init__(self, *, deps: AppDeps, lock_ttl_seconds: int = 30) -> None:
        self._deps = deps
        self._lock_ttl_seconds = max(5, int(lock_ttl_seconds))
        self._policy = PolicyEnforcer()

    def start_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        self._assert_not_terminal(run, action="started")
        run_mode = str(run.get("run_mode") or "plan_only").strip().lower()
        if not run_mode_supported(run_mode):
            raise AgentRuntimeError(f"Unsupported run_mode: {run_mode}")
        if run_mode == "plan_only":
            updated = self._deps.agent_runs.update_agent_run(
                run_id=run_id,
                status="planned",
                last_heartbeat_at=None,
                error=None,
            )
            return RuntimeResult(
                run=updated or run,
                message=(
                    "Run is in plan-only mode. Actions can be approved/rejected but "
                    "not executed."
                ),
            )
        updated = self._deps.agent_runs.update_agent_run(
            run_id=run_id, status="running", error=None
        )
        record_run_event(
            deps=self._deps,
            run_id=run_id,
            sequence=0,
            event_type="run_started",
            status="running",
            note="Run started",
        )
        return RuntimeResult(run=updated or run)

    def pause_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        self._assert_not_terminal(run, action="paused")
        updated = self._deps.agent_runs.update_agent_run(run_id=run_id, status="paused")
        record_run_event(
            deps=self._deps,
            run_id=run_id,
            sequence=0,
            event_type="run_paused",
            status="paused",
            note="Run paused",
        )
        record_operator_pause_condition(deps=self._deps, run=updated or run)
        return RuntimeResult(run=updated or run)

    def cancel_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        if self._normalized_status(run) in _TERMINAL_STATUSES:
            raise AgentRuntimeError("Run is already terminal")
        updated = self._deps.agent_runs.update_agent_run(
            run_id=run_id,
            status="canceled",
            error=None,
        )
        record_run_event(
            deps=self._deps,
            run_id=run_id,
            sequence=0,
            event_type="run_canceled",
            status="canceled",
            note="Run canceled",
        )
        return RuntimeResult(run=updated or run)

    def step_once(self, *, run_id: str, user_id: Optional[str]) -> RuntimeResult:
        run = self._require_run(run_id)
        run_mode = str(run.get("run_mode") or "plan_only").strip().lower()
        if not run_mode_supported(run_mode):
            raise AgentRuntimeError(f"Unsupported run_mode: {run_mode}")
        if run_mode == "plan_only":
            raise PlanOnlyModeError("Run is plan-only. Switch mode to execute steps.")
        if self._normalized_status(run) in _NON_EXECUTABLE_STATUSES:
            raise AgentRuntimeError("Run is not executable in its current status")

        lock_token = str(uuid.uuid4())
        acquired = self._deps.agent_runs.acquire_run_lock(
            run_id=run_id,
            lock_token=lock_token,
            ttl_seconds=self._lock_ttl_seconds,
        )
        if not acquired:
            raise RunBusyError("Run is currently busy; try again shortly.")

        try:
            self._deps.agent_runs.heartbeat_run_lock(
                run_id=run_id,
                lock_token=lock_token,
                ttl_seconds=self._lock_ttl_seconds,
            )
            stop = apply_stopping_condition(deps=self._deps, run=run)
            if stop:
                raise NoApprovedActionError(stop.note)
            action = self._claim_next_approved_action(run_id=run_id)
            if not action:
                status = compute_next_run_status(
                    deps=self._deps, run=run, run_id=run_id
                )
                self._deps.agent_runs.update_agent_run(
                    run_id=run_id,
                    status=status,
                    error=None,
                )
                raise NoApprovedActionError("No approved action to execute")
            self._deps.agent_runs.update_agent_run(
                run_id=run_id, status="running", error=None
            )
            record_action_event(
                deps=self._deps,
                run_id=run_id,
                action=action,
                event_type="action_executing",
                status="executing",
                note=action.get("rationale"),
            )

            capability_name = str(action.get("capability_name") or "")
            spec = get_capability_spec(capability_name)
            all_actions = self._deps.agent_actions.list_agent_actions(
                agent_run_id=run_id, limit=500
            )
            execution_state = AuthorizedExecutionState()
            try:
                if not spec:
                    raise AgentRuntimeError(
                        f"Unsupported capability: {capability_name}"
                    )
                try:
                    validate_harness_memory_policy(
                        harness_profile=get_harness_profile(run.get("harness_id"))
                        or {},
                        allowed_capabilities=[capability_name],
                    )
                except HarnessPostureError as exc:
                    raise AgentRuntimeError(str(exc)) from exc
                inputs = spec.normalize_inputs(action.get("inputs") or {})
                self._policy.validate_action_preflight(
                    run=run, action=action, spec=spec
                )
                execution_state.authorization = validate_exact_action_approval(
                    deps=self._deps,
                    run=run,
                    action=action,
                    spec=spec,
                )
                self._policy.validate_action_execution(
                    run=run,
                    action=action,
                    spec=spec,
                    all_actions=all_actions,
                    inputs=inputs,
                    approval_authorized=execution_state.authorization is not None,
                )
                outputs = execute_with_exact_authorization(
                    deps=self._deps,
                    run=run,
                    action=action,
                    spec=spec,
                    inputs=inputs,
                    user_id=user_id,
                    state=execution_state,
                )
            except ApprovalAuthorizationError as exc:
                record_approval_authorization_failure(
                    deps=self._deps,
                    run=run,
                    action=action,
                    error=exc,
                    state=execution_state,
                )
                raise AgentRuntimeError(str(exc)) from exc
            except PolicyError as exc:
                stop = record_policy_failure_and_stop(
                    deps=self._deps,
                    run=run,
                    action=action,
                    error=str(exc),
                )
                if stop:
                    raise AgentRuntimeError(stop.note) from exc
                self._deps.agent_runs.update_agent_run(
                    run_id=run_id,
                    status="failed",
                    error=str(exc),
                )
                raise AgentRuntimeError(str(exc)) from exc
            except AgentRuntimeError as exc:
                record_runtime_failure(
                    deps=self._deps,
                    run=run,
                    action=action,
                    error=str(exc),
                )
                raise AgentRuntimeError(str(exc)) from exc
            except CapabilityExecutionError as exc:
                record_capability_failure(
                    deps=self._deps,
                    run=run,
                    action=action,
                    state=execution_state,
                    error=str(exc),
                    error_code="capability_execution_error",
                )
                raise
            except ValueError as exc:
                record_capability_failure(
                    deps=self._deps,
                    run=run,
                    action=action,
                    state=execution_state,
                    error=str(exc),
                    error_code="capability_value_error",
                )
                raise CapabilityExecutionError(str(exc)) from exc

            if execution_state.authorization is None:
                executed = self._deps.agent_actions.update_agent_action_status(
                    action_id=str(action.get("id") or ""),
                    status="executed",
                    outputs=outputs,
                    outputs_hash=hash_payload(outputs),
                )
                record_action_event(
                    deps=self._deps,
                    run_id=run_id,
                    action=executed or action,
                    event_type="action_executed",
                    status="executed",
                    note=(executed or action).get("rationale"),
                )
            else:
                executed = self._deps.agent_actions.get_agent_action(
                    action_id=str(action.get("id") or ""),
                    client_id=str(run.get("client_id") or ""),
                )
            next_state = next_state_for_capability(capability_name)
            if next_state:
                self._deps.agent_runs.update_agent_run(run_id=run_id, state=next_state)
            refreshed_run = self._require_run(run_id)
            status = compute_next_run_status(
                deps=self._deps, run=refreshed_run, run_id=run_id
            )
            updated_run = self._deps.agent_runs.update_agent_run(
                run_id=run_id,
                status=status,
                error=None,
            )
            self._deps.agent_runs.heartbeat_run_lock(
                run_id=run_id,
                lock_token=lock_token,
                ttl_seconds=self._lock_ttl_seconds,
            )
            return RuntimeResult(
                run=updated_run or self._require_run(run_id), action=executed
            )
        finally:
            self._deps.agent_runs.release_run_lock(run_id=run_id, lock_token=lock_token)

    def reconcile_run_status(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        status = compute_next_run_status(deps=self._deps, run=run, run_id=run_id)
        updated = self._deps.agent_runs.update_agent_run(
            run_id=run_id,
            status=status,
            error=None if status != "failed" else run.get("error"),
        )
        return RuntimeResult(run=updated or run)

    def _require_run(self, run_id: str) -> Dict[str, Any]:
        run = self._deps.agent_runs.get_agent_run(run_id=run_id)
        if not run:
            raise RunNotFoundError("Agent run not found")
        return run

    def _normalized_status(self, run: Dict[str, Any]) -> str:
        status = str(run.get("status") or "").strip().lower()
        return "canceled" if status == "cancelled" else status

    def _assert_not_terminal(self, run: Dict[str, Any], *, action: str) -> None:
        if self._normalized_status(run) in _TERMINAL_STATUSES:
            raise AgentRuntimeError(f"Terminal runs cannot be {action}")

    def _claim_next_approved_action(self, *, run_id: str) -> Dict[str, Any] | None:
        actions = self._deps.agent_actions.list_agent_actions(
            agent_run_id=run_id, limit=500
        )
        approved = [item for item in actions if item.get("status") == "approved"]
        for item in approved:
            claimed = self._deps.agent_actions.transition_agent_action_status(
                action_id=str(item.get("id") or ""),
                from_status="approved",
                to_status="executing",
            )
            if claimed:
                return claimed
        return None


__all__ = [
    "AgentRuntimeService",
    "AgentRuntimeError",
    "RunNotFoundError",
    "PlanOnlyModeError",
    "RunBusyError",
    "NoApprovedActionError",
    "RuntimeResult",
]
