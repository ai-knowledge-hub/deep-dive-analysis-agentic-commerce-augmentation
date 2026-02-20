from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities import (
    CapabilityContext,
    CapabilityExecutionError,
    execute_capability,
)
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import (
    get_capability_spec,
    next_state_for_capability,
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


@dataclass(frozen=True)
class RuntimeResult:
    run: Dict[str, Any]
    action: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


def _hash_payload(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except Exception:
        encoded = str(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class AgentRuntimeService:
    def __init__(self, *, deps: AppDeps, lock_ttl_seconds: int = 30) -> None:
        self._deps = deps
        self._lock_ttl_seconds = max(5, int(lock_ttl_seconds))
        self._policy = PolicyEnforcer()

    def start_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        run_mode = str(run.get("run_mode") or "plan_only")
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
        return RuntimeResult(run=updated or run)

    def pause_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        updated = self._deps.agent_runs.update_agent_run(run_id=run_id, status="paused")
        return RuntimeResult(run=updated or run)

    def cancel_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        updated = self._deps.agent_runs.update_agent_run(
            run_id=run_id,
            status="canceled",
            error=None,
        )
        return RuntimeResult(run=updated or run)

    def step_once(self, *, run_id: str, user_id: Optional[str]) -> RuntimeResult:
        run = self._require_run(run_id)
        run_mode = str(run.get("run_mode") or "plan_only")
        if run_mode == "plan_only":
            raise PlanOnlyModeError("Run is plan-only. Switch mode to execute steps.")
        if str(run.get("status") or "").lower() in {"canceled", "completed"}:
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
            self._deps.agent_runs.update_agent_run(
                run_id=run_id, status="running", error=None
            )
            self._deps.agent_runs.heartbeat_run_lock(
                run_id=run_id,
                lock_token=lock_token,
                ttl_seconds=self._lock_ttl_seconds,
            )
            action = self._claim_next_approved_action(run_id=run_id)
            if not action:
                raise NoApprovedActionError("No approved action to execute")

            capability_name = str(action.get("capability_name") or "")
            spec = get_capability_spec(capability_name)
            if not spec:
                raise AgentRuntimeError(f"Unsupported capability: {capability_name}")
            inputs = spec.normalize_inputs(action.get("inputs") or {})
            all_actions = self._deps.agent_actions.list_agent_actions(
                agent_run_id=run_id, limit=500
            )
            self._policy.validate_action_execution(
                run=run,
                action=action,
                spec=spec,
                all_actions=all_actions,
                inputs=inputs,
            )
            context = CapabilityContext(
                client_id=str(run.get("client_id") or ""),
                user_id=user_id,
            )
            try:
                outputs = execute_capability(
                    deps=self._deps,
                    context=context,
                    capability_name=capability_name,
                    inputs=inputs,
                )
            except PolicyError as exc:
                self._deps.agent_actions.update_agent_action_status(
                    action_id=str(action.get("id") or ""),
                    status="failed",
                    outputs={},
                    outputs_hash=_hash_payload({}),
                    error=str(exc),
                )
                self._deps.agent_runs.update_agent_run(
                    run_id=run_id,
                    status="failed",
                    error=str(exc),
                )
                raise AgentRuntimeError(str(exc)) from exc
            except CapabilityExecutionError as exc:
                self._deps.agent_actions.update_agent_action_status(
                    action_id=str(action.get("id") or ""),
                    status="failed",
                    outputs={},
                    outputs_hash=_hash_payload({}),
                    error=str(exc),
                )
                self._deps.agent_runs.update_agent_run(
                    run_id=run_id,
                    status="failed",
                    error=str(exc),
                )
                raise
            except ValueError as exc:
                self._deps.agent_actions.update_agent_action_status(
                    action_id=str(action.get("id") or ""),
                    status="failed",
                    outputs={},
                    outputs_hash=_hash_payload({}),
                    error=str(exc),
                )
                self._deps.agent_runs.update_agent_run(
                    run_id=run_id,
                    status="failed",
                    error=str(exc),
                )
                raise CapabilityExecutionError(str(exc)) from exc

            executed = self._deps.agent_actions.update_agent_action_status(
                action_id=str(action.get("id") or ""),
                status="executed",
                outputs=outputs,
                outputs_hash=_hash_payload(outputs),
            )
            next_state = next_state_for_capability(capability_name)
            if next_state:
                self._deps.agent_runs.update_agent_run(run_id=run_id, state=next_state)
            status = self._compute_next_run_status(run_id=run_id)
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

    def _require_run(self, run_id: str) -> Dict[str, Any]:
        run = self._deps.agent_runs.get_agent_run(run_id=run_id)
        if not run:
            raise RunNotFoundError("Agent run not found")
        return run

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

    def _compute_next_run_status(self, *, run_id: str) -> str:
        actions = self._deps.agent_actions.list_agent_actions(
            agent_run_id=run_id, limit=500
        )
        statuses = {str(item.get("status") or "").lower() for item in actions}
        if "failed" in statuses:
            return "failed"
        if "approved" in statuses or "executing" in statuses:
            return "running"
        if "proposed" in statuses:
            return "planned"
        if statuses and statuses.issubset({"executed", "rejected"}):
            return "completed"
        return "running"


__all__ = [
    "AgentRuntimeService",
    "AgentRuntimeError",
    "RunNotFoundError",
    "PlanOnlyModeError",
    "RunBusyError",
    "NoApprovedActionError",
    "RuntimeResult",
]
