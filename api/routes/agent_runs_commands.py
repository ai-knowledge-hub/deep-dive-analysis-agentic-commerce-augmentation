from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.approval_authority import require_approval_authority
from api.utils.agent_run_authorization import require_agent_run_control_access
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.commands import (
    AgentRunCommandError,
    issue_agent_run_command as issue_agent_run_command_service,
    preflight_agent_run_command as preflight_agent_run_command_service,
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


class AgentRunCommandRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    command_type: str = Field(..., min_length=1)
    action_id: Optional[str] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    idempotency_key: Optional[str] = None


@router.post("/{run_id}/commands/preflight")
def preflight_agent_run_command(
    run_id: str,
    payload: AgentRunCommandRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=scoped_client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=payload.user_id,
        required_scope="agent_runs:read",
    )
    try:
        return preflight_agent_run_command_service(
            deps=deps,
            run_id=run_id,
            client_id=scoped_client_id,
            command_type=payload.command_type,
            action_id=payload.action_id,
            metadata=payload.metadata,
        )
    except AgentRunCommandError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.post("/{run_id}/commands")
def issue_agent_run_command(
    run_id: str,
    payload: AgentRunCommandRequest,
    request: Request,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=scoped_client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    normalized_command = payload.command_type.strip().lower()
    approving_authority = None
    if normalized_command in {"approve", "reject", "reconcile_effect"}:
        approving_authority = require_approval_authority(
            request=request,
            run=run,
            client_id=scoped_client_id,
            user_id=payload.user_id,
        )
    else:
        require_agent_run_control_access(
            request=request,
            run=run,
            client_id=scoped_client_id,
            user_id=payload.user_id,
            required_scope="agent_runs:write",
        )
    try:
        return issue_agent_run_command_service(
            deps=deps,
            runtime=runtime,
            run_id=run_id,
            client_id=scoped_client_id,
            user_id=payload.user_id,
            command_type=payload.command_type,
            action_id=payload.action_id,
            message=payload.message,
            metadata=payload.metadata,
            approving_authority=approving_authority,
            idempotency_key=payload.idempotency_key,
        )
    except AgentRunCommandError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PlanOnlyModeError, NoApprovedActionError, RunBusyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CapabilityExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
