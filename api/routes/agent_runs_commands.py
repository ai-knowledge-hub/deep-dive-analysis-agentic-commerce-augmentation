from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.commands import (
    _command_preflight,
    _record_command_event,
)
from application.services.agent_runtime.commands.decisions import (
    apply_command_action_decision,
    decide_agent_action,
)
from application.services.agent_runtime.commands.recovery import (
    create_change_plan_recovery_action,
    create_retry_action,
)
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
    NoApprovedActionError,
    PlanOnlyModeError,
    RunBusyError,
    RunNotFoundError,
)


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def _deps() -> AppDeps:
    return default_deps()


def _runtime(deps: AppDeps = Depends(_deps)) -> AgentRuntimeService:
    return AgentRuntimeService(deps=deps)


def _require_scoped_run(
    *, deps: AppDeps, run_id: str, client_id: str
) -> Dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


class AgentActionDecisionRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    decision: str = Field(..., min_length=1)  # approve|reject


class AgentRunCommandRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    command_type: str = Field(..., min_length=1)
    action_id: Optional[str] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@router.post("/{run_id}/commands/preflight")
def preflight_agent_run_command(
    run_id: str,
    payload: AgentRunCommandRequest,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    command_type = str(payload.command_type or "").strip().lower()
    allowed_commands = {
        "explain",
        "focus",
        "change_plan",
        "start",
        "pause",
        "cancel",
        "step",
        "approve",
        "reject",
        "retry",
    }
    if command_type not in allowed_commands:
        raise HTTPException(status_code=400, detail="Unsupported command")

    action = None
    if payload.action_id:
        action = deps.agent_actions.get_agent_action(
            action_id=payload.action_id,
            client_id=scoped_client_id,
        )
        if not action or str(action.get("agent_run_id") or "") != run_id:
            raise HTTPException(status_code=404, detail="Agent action not found")

    return {
        "preflight": _command_preflight(
            deps=deps,
            run=run,
            command_type=command_type,
            action=action,
            metadata=payload.metadata,
        ),
        "run": run,
        "action": action,
    }


@router.post("/{run_id}/commands")
def issue_agent_run_command(
    run_id: str,
    payload: AgentRunCommandRequest,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    command_type = str(payload.command_type or "").strip().lower()
    allowed_commands = {
        "explain",
        "focus",
        "change_plan",
        "start",
        "pause",
        "cancel",
        "step",
        "approve",
        "reject",
        "retry",
    }
    if command_type not in allowed_commands:
        raise HTTPException(status_code=400, detail="Unsupported command")

    action = None
    if payload.action_id:
        action = deps.agent_actions.get_agent_action(
            action_id=payload.action_id,
            client_id=scoped_client_id,
        )
        if not action or str(action.get("agent_run_id") or "") != run_id:
            raise HTTPException(status_code=404, detail="Agent action not found")

    preflight = _command_preflight(
        deps=deps,
        run=run,
        command_type=command_type,
        action=action,
        metadata=payload.metadata,
    )
    if not preflight["allowed"]:
        raise HTTPException(status_code=409, detail=preflight)

    receipt = _record_command_event(
        deps=deps,
        run=run,
        command_type=command_type,
        status="received",
        action=action,
        note=payload.message or f"Operator chat command: {command_type}",
        metadata=payload.metadata,
    )
    result: Dict[str, Any] = {"command": receipt, "run": run, "preflight": preflight}

    if command_type in {"explain", "focus"}:
        return result

    try:
        if command_type == "change_plan":
            result["action"] = create_change_plan_recovery_action(
                deps=deps,
                run_id=run_id,
                run=run,
                source_action=action,
                command_receipt=receipt,
                message=payload.message,
                metadata=payload.metadata,
            )
        elif command_type == "start":
            runtime_result = runtime.start_run(run_id=run_id)
            result["run"] = runtime_result.run
            result["message"] = runtime_result.message
        elif command_type == "pause":
            runtime_result = runtime.pause_run(run_id=run_id)
            result["run"] = runtime_result.run
        elif command_type == "cancel":
            runtime_result = runtime.cancel_run(run_id=run_id)
            result["run"] = runtime_result.run
        elif command_type == "step":
            runtime_result = runtime.step_once(run_id=run_id, user_id=payload.user_id)
            result["run"] = runtime_result.run
            result["action"] = runtime_result.action
        elif command_type == "retry":
            if not action:
                raise HTTPException(status_code=400, detail="Action id is required")
            result["action"] = create_retry_action(
                deps=deps,
                run_id=run_id,
                run=run,
                action=action,
                metadata=payload.metadata,
            )
        elif command_type in {"approve", "reject"}:
            if not action:
                raise HTTPException(status_code=400, detail="Action id is required")
            result["action"] = apply_command_action_decision(
                deps=deps,
                run_id=run_id,
                run=run,
                action=action,
                command_type=command_type,
            )
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PlanOnlyModeError, NoApprovedActionError, RunBusyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CapabilityExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    _record_command_event(
        deps=deps,
        run=result.get("run") or run,
        command_type=command_type,
        status="completed",
        action=result.get("action") or action,
        note=f"Operator chat command completed: {command_type}",
        metadata=payload.metadata,
    )
    return result


@router.post("/actions/{action_id}/decision")
def decide_action(
    action_id: str,
    payload: AgentActionDecisionRequest,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    try:
        action = decide_agent_action(
            deps=deps,
            action_id=action_id,
            client_id=scoped_client_id,
            user_id=payload.user_id,
            decision=payload.decision,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "Agent action not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"action": action}
