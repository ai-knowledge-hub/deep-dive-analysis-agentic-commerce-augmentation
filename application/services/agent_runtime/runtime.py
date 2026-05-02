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
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    skill_id_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.registry import (
    get_capability_spec,
    next_state_for_capability,
    validate_outputs,
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
        self._record_run_event(
            run_id=run_id,
            sequence=0,
            event_type="run_started",
            status="running",
            note="Run started",
        )
        return RuntimeResult(run=updated or run)

    def pause_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        updated = self._deps.agent_runs.update_agent_run(run_id=run_id, status="paused")
        self._record_run_event(
            run_id=run_id,
            sequence=0,
            event_type="run_paused",
            status="paused",
            note="Run paused",
        )
        return RuntimeResult(run=updated or run)

    def cancel_run(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        updated = self._deps.agent_runs.update_agent_run(
            run_id=run_id,
            status="canceled",
            error=None,
        )
        self._record_run_event(
            run_id=run_id,
            sequence=0,
            event_type="run_canceled",
            status="canceled",
            note="Run canceled",
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
            self._record_action_event(
                run_id=run_id,
                action=action,
                event_type="action_executing",
                status="executing",
                note=action.get("rationale"),
            )

            capability_name = str(action.get("capability_name") or "")
            spec = get_capability_spec(capability_name)
            if not spec:
                raise AgentRuntimeError(f"Unsupported capability: {capability_name}")
            inputs = spec.normalize_inputs(action.get("inputs") or {})
            all_actions = self._deps.agent_actions.list_agent_actions(
                agent_run_id=run_id, limit=500
            )
            try:
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
                outputs = execute_capability(
                    deps=self._deps,
                    context=context,
                    capability_name=capability_name,
                    inputs=inputs,
                )
                output_errors = validate_outputs(spec, outputs)
                if output_errors:
                    raise CapabilityExecutionError("; ".join(output_errors))
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
                self._record_action_event(
                    run_id=run_id,
                    action=action,
                    event_type="action_failed",
                    status="failed",
                    note=str(exc),
                    is_policy_event=True,
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
                self._record_action_event(
                    run_id=run_id,
                    action=action,
                    event_type="action_failed",
                    status="failed",
                    note=str(exc),
                    is_policy_event=False,
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
                self._record_action_event(
                    run_id=run_id,
                    action=action,
                    event_type="action_failed",
                    status="failed",
                    note=str(exc),
                    is_policy_event=False,
                )
                raise CapabilityExecutionError(str(exc)) from exc

            executed = self._deps.agent_actions.update_agent_action_status(
                action_id=str(action.get("id") or ""),
                status="executed",
                outputs=outputs,
                outputs_hash=_hash_payload(outputs),
            )
            self._record_action_event(
                run_id=run_id,
                action=executed or action,
                event_type="action_executed",
                status="executed",
                note=(executed or action).get("rationale"),
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

    def reconcile_run_status(self, *, run_id: str) -> RuntimeResult:
        run = self._require_run(run_id)
        status = self._compute_next_run_status(run_id=run_id)
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

    def _record_run_event(
        self,
        *,
        run_id: str,
        sequence: int,
        event_type: str,
        status: str,
        note: Optional[str],
    ) -> None:
        run = self._deps.agent_runs.get_agent_run(run_id=run_id) or {}
        self._deps.agent_events.create_agent_event(
            agent_run_id=run_id,
            action_id=None,
            sequence=sequence,
            event_type=event_type,
            status=status,
            capability_name=None,
            capability_version=None,
            principal_type=run.get("principal_type"),
            principal_id=run.get("principal_id"),
            trace_id=run.get("trace_id"),
            note=note,
            is_policy_event=False,
            anchors={},
        )

    def _record_action_event(
        self,
        *,
        run_id: str,
        action: Dict[str, Any],
        event_type: str,
        status: str,
        note: Optional[str],
        is_policy_event: bool = False,
    ) -> None:
        run = self._deps.agent_runs.get_agent_run(run_id=run_id) or {}
        outputs = action.get("outputs") or {}
        metric_id = None
        if isinstance(outputs, dict):
            metric_id = (
                outputs.get("metric_id")
                or outputs.get("new_metric_id")
                or outputs.get("source_metric_id")
            )
        self._deps.agent_events.create_agent_event(
            agent_run_id=run_id,
            action_id=str(action.get("id") or "") or None,
            sequence=int(action.get("sequence") or 0),
            event_type=event_type,
            status=status,
            capability_name=str(action.get("capability_name") or "") or None,
            capability_version=str(action.get("capability_version") or "") or None,
            principal_type=run.get("principal_type"),
            principal_id=run.get("principal_id"),
            tool_id=action.get("tool_id")
            or capability_to_tool_id(str(action.get("capability_name") or "")),
            skill_id=action.get("skill_id")
            or skill_id_for_tool_id(
                action.get("tool_id")
                or capability_to_tool_id(str(action.get("capability_name") or ""))
            ),
            effect_class=action.get("effect_class")
            or tool_effect_class(
                action.get("tool_id")
                or capability_to_tool_id(str(action.get("capability_name") or ""))
            ),
            trace_id=run.get("trace_id"),
            note=str(note) if note is not None else None,
            is_policy_event=is_policy_event,
            anchors={
                "experiment_id": run.get("experiment_id"),
                "variant_id": action.get("variant_id"),
                "validation_job_id": action.get("validation_job_id"),
                "hypothesis_id": action.get("hypothesis_id"),
                "snapshot_version": action.get("snapshot_version"),
                "metric_id": metric_id,
            },
        )


__all__ = [
    "AgentRuntimeService",
    "AgentRuntimeError",
    "RunNotFoundError",
    "PlanOnlyModeError",
    "RunBusyError",
    "NoApprovedActionError",
    "RuntimeResult",
]
