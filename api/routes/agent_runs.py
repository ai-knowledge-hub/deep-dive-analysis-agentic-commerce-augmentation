from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.tenancy import require_client_id
from application.services.agent_runtime.capabilities import (
    CapabilityExecutionError,
)
from application.services.agent_runtime.planner import build_initial_plan
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
    NoApprovedActionError,
    PlanOnlyModeError,
    RunBusyError,
    RunNotFoundError,
)


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])

DEPS = default_deps()
RUNTIME = AgentRuntimeService(deps=DEPS)


class AgentRunCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    experiment_id: Optional[str] = None

    objective: Dict[str, Any] = Field(default_factory=dict)
    allowed_capabilities: List[str] = Field(default_factory=list)
    capability_versions: Dict[str, Any] = Field(default_factory=dict)
    budgets: Dict[str, Any] = Field(default_factory=dict)
    approval_policy: Dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = True
    run_mode: str = "plan_only"  # plan_only|auto_execute_safe

    state: str = "battery_ready"
    status: str = "planned"


class AgentRunListResponse(BaseModel):
    runs: List[Dict[str, Any]]


class AgentRunDetailResponse(BaseModel):
    run: Dict[str, Any]
    actions: List[Dict[str, Any]]


class AgentActionDecisionRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    decision: str = Field(..., min_length=1)  # approve|reject


class AgentRunControlRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None


def _hash_payload(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except Exception:
        encoded = str(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@router.post("")
def create_agent_run(payload: AgentRunCreateRequest) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    run = DEPS.agent_runs.create_agent_run(
        client_id=client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        experiment_id=payload.experiment_id,
        objective=payload.objective or {},
        allowed_capabilities=payload.allowed_capabilities or [],
        capability_versions=payload.capability_versions or {},
        budgets=payload.budgets or {},
        approval_policy=payload.approval_policy or {},
        requires_approval=bool(payload.requires_approval),
        run_mode=str(payload.run_mode or "plan_only").strip().lower(),
        state=str(payload.state or "battery_ready"),
        status=str(payload.status or "planned"),
    )

    # v0 behavior: seed a human-reviewable plan as proposed actions.
    plan = build_initial_plan(
        experiment_id=payload.experiment_id,
        allowed_capabilities=payload.allowed_capabilities or [],
        capability_versions=payload.capability_versions or {},
    )
    for idx, action in enumerate(plan, start=1):
        DEPS.agent_actions.create_agent_action(
            agent_run_id=run.get("id"),
            sequence=idx,
            status="proposed",
            capability_name=action.capability_name,
            capability_version=action.capability_version,
            inputs=action.inputs,
            outputs={},
            inputs_hash=_hash_payload(action.inputs),
            outputs_hash=None,
            rationale=action.rationale,
            confidence=action.confidence,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
        )
    return {"run": run}


@router.post("/{run_id}/start")
def start_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    try:
        result = RUNTIME.start_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run, "message": result.message}


@router.post("/{run_id}/pause")
def pause_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    try:
        result = RUNTIME.pause_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run}


@router.post("/{run_id}/cancel")
def cancel_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    try:
        result = RUNTIME.cancel_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run}


@router.post("/{run_id}/step")
def step_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    try:
        result = RUNTIME.step_once(
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


@router.get("")
def list_agent_runs(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> AgentRunListResponse:
    resolved = require_client_id(client_id, user_id)
    runs = DEPS.agent_runs.list_agent_runs(
        client_id=resolved,
        experiment_id=experiment_id,
        product_id=product_id,
        status=status,
        limit=limit,
    )
    return AgentRunListResponse(runs=runs)


@router.get("/{run_id}")
def get_agent_run(
    run_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 200,
) -> AgentRunDetailResponse:
    require_client_id(client_id, user_id)
    run = DEPS.agent_runs.get_agent_run(run_id=run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    actions = DEPS.agent_actions.list_agent_actions(agent_run_id=run_id, limit=limit)
    return AgentRunDetailResponse(run=run, actions=actions)


@router.post("/actions/{action_id}/decision")
def decide_action(
    action_id: str,
    payload: AgentActionDecisionRequest,
) -> Dict[str, Any]:
    require_client_id(payload.client_id, payload.user_id)
    action = DEPS.agent_actions.get_agent_action(action_id=action_id)
    if not action:
        raise HTTPException(status_code=404, detail="Agent action not found")
    decision = str(payload.decision or "").strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Invalid decision")
    updated = DEPS.agent_actions.update_agent_action_status(
        action_id=action_id,
        status="approved" if decision == "approve" else "rejected",
    )
    return {"action": updated or action}
