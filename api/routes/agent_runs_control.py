from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from api.composition import default_deps
from api.utils.agent_run_authorization import require_agent_run_control_access
from api.utils.tenancy import require_admin, require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
    NoApprovedActionError,
    PlanOnlyModeError,
    RunBusyError,
    RunNotFoundError,
)
from application.services.agent_runtime.worker import AgentRuntimeWorkerService


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def _deps() -> AppDeps:
    return default_deps()


def _runtime(deps: AppDeps = Depends(_deps)) -> AgentRuntimeService:
    return AgentRuntimeService(deps=deps)


def _worker(deps: AppDeps = Depends(_deps)) -> AgentRuntimeWorkerService:
    return AgentRuntimeWorkerService(deps=deps)


class AgentRunControlRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None


class AgentRunTickRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    max_runs: int = 10
    max_steps_per_run: int = 5


def _require_scoped_run(
    *, deps: AppDeps, run_id: str, client_id: str
) -> Dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


@router.post("/{run_id}/start")
def start_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    request: Request,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=payload.user_id,
        required_scope="agent_runs:write",
    )
    try:
        result = runtime.start_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run, "message": result.message}


@router.post("/{run_id}/pause")
def pause_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    request: Request,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=payload.user_id,
        required_scope="agent_runs:write",
    )
    try:
        result = runtime.pause_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run}


@router.post("/{run_id}/cancel")
def cancel_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    request: Request,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=payload.user_id,
        required_scope="agent_runs:write",
    )
    try:
        result = runtime.cancel_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run}


@router.post("/{run_id}/step")
def step_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    request: Request,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=payload.user_id,
        required_scope="agent_runs:write",
    )
    try:
        result = runtime.step_once(
            run_id=run_id,
            user_id=payload.user_id,
        )
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (PlanOnlyModeError, NoApprovedActionError, RunBusyError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except CapabilityExecutionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AgentRuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": result.run, "action": result.action}


@router.post("/tick")
def tick_agent_runs(
    payload: AgentRunTickRequest,
    worker: AgentRuntimeWorkerService = Depends(_worker),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    runnable = deps.agent_runs.list_runnable_agent_runs(
        client_id=client_id,
        limit=max(1, min(100, int(payload.max_runs))),
    )
    if any(str(run.get("principal_type") or "") == "external_agent" for run in runnable):
        require_admin(payload.user_id)
    summary = worker.tick_client(
        client_id=client_id,
        user_id=payload.user_id,
        max_runs=max(1, min(100, int(payload.max_runs))),
        max_steps_per_run=max(1, min(50, int(payload.max_steps_per_run))),
    )
    return summary
