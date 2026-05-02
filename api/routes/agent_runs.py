from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.principals import resolve_principal_context
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.capabilities import (
    CapabilityExecutionError,
)
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    list_skill_specs,
    new_trace_id,
    policy_profile_for_run_mode,
    skill_id_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.events import list_agent_run_events_page
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.planner import build_initial_plan
from application.services.agent_runtime.registry import (
    get_capability_spec,
    list_capability_specs,
    list_tool_specs,
)
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


def _require_scoped_run(*, deps: AppDeps, run_id: str, client_id: str) -> Dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


class AgentRunCreateRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    experiment_id: Optional[str] = None
    principal_type: Optional[str] = None
    principal_id: Optional[str] = None
    agent_profile_id: Optional[str] = None
    harness_id: Optional[str] = None
    policy_profile_id: Optional[str] = None
    idempotency_key: Optional[str] = None

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


class AgentRunEventListResponse(BaseModel):
    events: List[Dict[str, Any]]
    page: Dict[str, Any]


class AgentActionDecisionRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    decision: str = Field(..., min_length=1)  # approve|reject


class AgentRunControlRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None


class AgentRunTickRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    max_runs: int = 10
    max_steps_per_run: int = 5


class AgentRunCommandRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    command_type: str = Field(..., min_length=1)
    action_id: Optional[str] = None
    message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def _serialize_spec(value: Any) -> Dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    return dict(getattr(value, "__dict__", {}))


def _hash_payload(value: Any) -> str:
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    except Exception:
        encoded = str(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _record_command_event(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    command_type: str,
    status: str,
    action: Optional[Dict[str, Any]] = None,
    note: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return deps.agent_events.create_agent_event(
        agent_run_id=str(run.get("id") or ""),
        action_id=str(action.get("id") or "") if action else None,
        sequence=int(action.get("sequence") or 0) if action else 0,
        event_type=f"operator_command_{command_type}",
        status=status,
        capability_name=str(action.get("capability_name") or "") if action else None,
        capability_version=str(action.get("capability_version") or "") if action else None,
        principal_type=run.get("principal_type"),
        principal_id=run.get("principal_id"),
        tool_id=action.get("tool_id") if action else None,
        skill_id=(
            action.get("skill_id") or skill_id_for_tool_id(action.get("tool_id"))
            if action
            else None
        ),
        effect_class=action.get("effect_class") if action else None,
        trace_id=run.get("trace_id"),
        note=note or f"Operator command: {command_type}",
        is_policy_event=False,
        anchors={
            "experiment_id": run.get("experiment_id"),
            "variant_id": action.get("variant_id") if action else None,
            "validation_job_id": action.get("validation_job_id") if action else None,
            "hypothesis_id": action.get("hypothesis_id") if action else None,
            "snapshot_version": action.get("snapshot_version") if action else None,
            "metric_id": None,
            "command_type": command_type,
            "metadata": metadata or {},
        },
    )


def _command_preflight(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    command_type: str,
    action: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    run_status = str(run.get("status") or "").lower()
    run_mode = str(run.get("run_mode") or "plan_only").lower()
    effect_class = action.get("effect_class") if action else None
    tool_id = action.get("tool_id") if action else None
    capability_name = str(action.get("capability_name") or "") if action else None
    spec = get_capability_spec(capability_name or "") if capability_name else None
    if spec:
        effect_class = effect_class or spec.effect_class
        tool_id = tool_id or spec.tool_id

    blockers: List[str] = []
    warnings: List[str] = []
    side_effects = list(spec.side_effects) if spec else []

    if command_type in {"approve", "reject", "retry"} and not action:
        blockers.append("This command requires an action_id.")
    if command_type == "approve" and action:
        if str(action.get("status") or "").lower() != "proposed":
            blockers.append("Only proposed actions can be approved.")
    if command_type == "reject" and action:
        if str(action.get("status") or "").lower() not in {"proposed", "approved"}:
            blockers.append("Only proposed or approved actions can be rejected.")
    if command_type == "retry" and action:
        if str(action.get("status") or "").lower() != "failed":
            blockers.append("Retry is only available for failed actions.")
    if command_type == "step":
        if run_mode == "plan_only":
            blockers.append("Run is plan-only. Switch mode before executing steps.")
        if run_status in {"canceled", "completed"}:
            blockers.append("Run is not executable in its current status.")
    if command_type == "start" and run_status in {"canceled", "completed"}:
        blockers.append("Canceled or completed runs cannot be started.")
    if command_type == "cancel" and run_status in {"canceled", "completed"}:
        blockers.append("Run is already terminal.")
    if command_type == "change_plan":
        allowed = [
            str(item).strip()
            for item in list(run.get("allowed_capabilities") or [])
            if str(item).strip()
        ]
        if not allowed:
            blockers.append("Change-plan needs at least one allowed recovery capability.")
        warnings.append(
            "Change-plan creates a proposed recovery action for operator review; it does not execute immediately."
        )

    if action and spec and command_type == "retry":
        inputs = spec.normalize_inputs(action.get("inputs") or {})
        all_actions = deps.agent_actions.list_agent_actions(
            agent_run_id=str(run.get("id") or ""), limit=500
        )
        try:
            PolicyEnforcer().validate_action_execution(
                run=run,
                action=action,
                spec=spec,
                all_actions=all_actions,
                inputs=inputs,
            )
        except PolicyError as exc:
            blockers.append(str(exc))
    elif action and spec:
        allowed_capabilities = {
            str(item).strip()
            for item in list(run.get("allowed_capabilities") or [])
            if str(item).strip()
        }
        if spec.name not in allowed_capabilities:
            blockers.append(f"Capability '{spec.name}' is not allowed for this run")
        if (
            str(run.get("policy_profile_id") or "").strip().lower() == "observe"
            and spec.effect_class not in {"read", "recommend"}
        ):
            blockers.append(
                f"Policy profile 'observe' forbids effect class '{spec.effect_class}' "
                f"for tool '{tool_id or '<unknown>'}'"
            )
    elif action and not spec:
        warnings.append(
            f"No executable capability spec was found for '{capability_name or 'unknown'}'."
        )

    if command_type in {"approve", "retry", "step"} and effect_class in {
        "write_high_risk",
        "external_side_effect",
    }:
        warnings.append(
            f"This command may trigger {effect_class} work through tool '{tool_id or 'unknown'}'."
        )
    if command_type == "cancel":
        warnings.append("Canceling a run is terminal and should be treated as an operator intervention.")
    if command_type == "pause":
        warnings.append("Pausing preserves state but stops autonomous progress until resumed.")

    risk_level = "low"
    if command_type == "cancel" or effect_class == "write_high_risk":
        risk_level = "high"
    elif effect_class == "external_side_effect" or command_type in {
        "change_plan",
        "retry",
        "step",
    }:
        risk_level = "medium"

    return {
        "allowed": not blockers,
        "command_type": command_type,
        "risk_level": risk_level,
        "requires_confirmation": command_type in {"retry", "step"}
        or risk_level == "high"
        or bool(blockers),
        "requires_approval": bool(run.get("requires_approval")) or risk_level == "high",
        "effect_class": effect_class,
        "tool_id": tool_id,
        "skill_id": action.get("skill_id") if action else None,
        "side_effects": side_effects,
        "blockers": blockers,
        "warnings": warnings,
        "rollback_guidance": _rollback_guidance(
            command_type=command_type,
            effect_class=str(effect_class or ""),
            side_effects=side_effects,
        ),
        "summary": _preflight_summary(
            command_type=command_type,
            risk_level=risk_level,
            blockers=blockers,
            warnings=warnings,
        ),
    }


def _rollback_guidance(
    *, command_type: str, effect_class: str, side_effects: List[str]
) -> str:
    if command_type == "reject":
        return "Rejection is reversible by creating a new proposed action if needed."
    if command_type == "pause":
        return "Resume with start once the operator is ready."
    if command_type == "cancel":
        return "Cancel is terminal. Create a new run to continue from the same objective."
    if effect_class == "write_high_risk":
        return "High-risk writes may need a compensating action or manual rollback after execution."
    if effect_class == "external_side_effect":
        return "External side effects may not be fully reversible; confirm provider/job state before retrying."
    if side_effects:
        return "Low-risk writes can usually be superseded by a later action, but the audit trail is permanent."
    return "No direct side effects are expected from this command."


def _preflight_summary(
    *, command_type: str, risk_level: str, blockers: List[str], warnings: List[str]
) -> str:
    if blockers:
        return f"Preflight blocked {command_type}: {blockers[0]}"
    if warnings:
        return f"Preflight passed with {risk_level} risk: {warnings[0]}"
    return f"Preflight passed with {risk_level} risk."


@router.get("/registry")
def get_agent_runtime_registry() -> Dict[str, Any]:
    skills = [_serialize_spec(skill) for skill in list_skill_specs()]
    tools = [_serialize_spec(tool) for tool in list_tool_specs()]
    capabilities = [_serialize_spec(capability) for capability in list_capability_specs()]
    skill_ids_by_tool: Dict[str, List[str]] = {}
    for skill in skills:
        for tool_id in skill.get("tool_ids", []) or []:
            skill_ids_by_tool.setdefault(str(tool_id), []).append(str(skill.get("id")))
    return {
        "skills": skills,
        "tools": tools,
        "capabilities": capabilities,
        "skill_ids_by_tool": skill_ids_by_tool,
        "policy_profiles": [
            {
                "id": "human_approval_required",
                "name": "Human Approval Required",
                "description": "Plan-first profile; proposed actions require operator approval before execution.",
                "auto_effect_classes": [],
            },
            {
                "id": "safe_auto",
                "name": "Safe Auto",
                "description": "Allows bounded execution for low-risk approved work while preserving gates for risky effects.",
                "auto_effect_classes": ["read", "recommend", "write_low_risk"],
            },
            {
                "id": "observe",
                "name": "Observe",
                "description": "Read-only profile for inspection, explanation, and audit workflows.",
                "auto_effect_classes": ["read", "recommend"],
            },
        ],
    }


@router.post("")
def create_agent_run(
    payload: AgentRunCreateRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    principal = resolve_principal_context(
        request=request,
        client_id=payload.client_id,
        user_id=payload.user_id,
        principal_type=payload.principal_type,
        principal_id=payload.principal_id,
        agent_profile_id=payload.agent_profile_id,
    )
    client_id = principal.client_id
    run_mode = str(payload.run_mode or "plan_only").strip().lower()
    policy_profile_id = payload.policy_profile_id or policy_profile_for_run_mode(run_mode)
    trace_id = new_trace_id()
    run = deps.agent_runs.create_agent_run(
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
        run_mode=run_mode,
        state=str(payload.state or "battery_ready"),
        status=str(payload.status or "planned"),
        principal_type=principal.principal_type,
        principal_id=principal.principal_id,
        agent_profile_id=principal.agent_profile_id,
        harness_id=payload.harness_id,
        policy_profile_id=policy_profile_id,
        idempotency_key=payload.idempotency_key,
        trace_id=trace_id,
    )

    # v0 behavior: seed a human-reviewable plan as proposed actions.
    plan = build_initial_plan(
        experiment_id=payload.experiment_id,
        allowed_capabilities=payload.allowed_capabilities or [],
        capability_versions=payload.capability_versions or {},
    )
    for idx, action in enumerate(plan, start=1):
        tool_id = capability_to_tool_id(action.capability_name)
        skill_id = skill_id_for_tool_id(tool_id)
        created_action = deps.agent_actions.create_agent_action(
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
            tool_id=tool_id,
            skill_id=skill_id,
            effect_class=tool_effect_class(tool_id),
        )
        deps.agent_events.create_agent_event(
            agent_run_id=run.get("id"),
            action_id=created_action.get("id"),
            sequence=idx,
            event_type="action_proposed",
            status="proposed",
            capability_name=action.capability_name,
            capability_version=action.capability_version,
            principal_type=run.get("principal_type"),
            principal_id=run.get("principal_id"),
            tool_id=created_action.get("tool_id"),
            skill_id=created_action.get("skill_id"),
            effect_class=created_action.get("effect_class"),
            trace_id=run.get("trace_id"),
            note=action.rationale,
            is_policy_event=False,
            anchors={
                "experiment_id": run.get("experiment_id"),
                "variant_id": None,
                "validation_job_id": None,
                "hypothesis_id": None,
                "snapshot_version": None,
                "metric_id": None,
            },
        )
    return {"run": run}


@router.post("/{run_id}/start")
def start_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    try:
        result = runtime.start_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run, "message": result.message}


@router.post("/{run_id}/pause")
def pause_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    try:
        result = runtime.pause_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run}


@router.post("/{run_id}/cancel")
def cancel_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    try:
        result = runtime.cancel_run(run_id=run_id)
    except RunNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"run": result.run}


@router.post("/{run_id}/step")
def step_agent_run(
    run_id: str,
    payload: AgentRunControlRequest,
    runtime: AgentRuntimeService = Depends(_runtime),
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
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
    payload: AgentRunTickRequest, worker: AgentRuntimeWorkerService = Depends(_worker)
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    summary = worker.tick_client(
        client_id=client_id,
        user_id=payload.user_id,
        max_runs=max(1, min(100, int(payload.max_runs))),
        max_steps_per_run=max(1, min(50, int(payload.max_steps_per_run))),
    )
    return summary


@router.get("")
def list_agent_runs(
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    deps: AppDeps = Depends(_deps),
) -> AgentRunListResponse:
    resolved = require_client_id(client_id, user_id)
    runs = deps.agent_runs.list_agent_runs(
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
    deps: AppDeps = Depends(_deps),
) -> AgentRunDetailResponse:
    scoped_client_id = require_client_id(client_id, user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=limit)
    return AgentRunDetailResponse(run=run, actions=actions)


@router.get("/{run_id}/events")
def get_agent_run_events(
    run_id: str,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 500,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    capability_name: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    event_id: Optional[str] = None,
    around: int = 120,
    deps: AppDeps = Depends(_deps),
) -> AgentRunEventListResponse:
    scoped_client_id = require_client_id(client_id, user_id)
    _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    try:
        page = list_agent_run_events_page(
            deps=deps,
            run_id=run_id,
            client_id=scoped_client_id,
            limit=max(1, min(int(limit), 2000)),
            event_type=event_type,
            status=status,
            capability_name=capability_name,
            since=since,
            until=until,
            before=before,
            after=after,
            event_id=event_id,
            around=max(1, min(int(around), 2000)),
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload = page.to_dict()
    return AgentRunEventListResponse(events=payload["events"], page=payload["page"])


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
            actions = deps.agent_actions.list_agent_actions(
                agent_run_id=run_id,
                limit=500,
            )
            next_sequence = max(
                [int(item.get("sequence") or 0) for item in actions] or [0]
            ) + 1
            allowed = [
                str(item).strip()
                for item in list(run.get("allowed_capabilities") or [])
                if str(item).strip()
            ]
            requested_capability = str(
                payload.metadata.get("capability_name") or ""
            ).strip()
            capability_name = (
                requested_capability
                if requested_capability in allowed
                else "recommend_next_action"
                if "recommend_next_action" in allowed
                else allowed[0]
            )
            tool_id = capability_to_tool_id(capability_name)
            recovery_inputs = payload.metadata.get("inputs")
            inputs = dict(recovery_inputs) if isinstance(recovery_inputs, dict) else {}
            if run.get("experiment_id") and not inputs.get("experiment_id"):
                inputs["experiment_id"] = run.get("experiment_id")
            recovery_action = deps.agent_actions.create_agent_action(
                agent_run_id=run_id,
                sequence=next_sequence,
                status="proposed",
                capability_name=capability_name,
                capability_version=None,
                inputs=inputs,
                outputs={},
                inputs_hash=_hash_payload(inputs),
                outputs_hash=None,
                rationale=payload.message
                or "Recovery action proposed from operator change-plan command.",
                confidence=0.5,
                snapshot_version=action.get("snapshot_version") if action else None,
                hypothesis_id=action.get("hypothesis_id") if action else None,
                variant_id=action.get("variant_id") if action else None,
                validation_job_id=action.get("validation_job_id") if action else None,
                tool_id=tool_id,
                skill_id=skill_id_for_tool_id(tool_id),
                effect_class=tool_effect_class(tool_id),
                dedupe_key=f"change_plan:{receipt.get('id')}",
            )
            deps.agent_events.create_agent_event(
                agent_run_id=run_id,
                action_id=str(recovery_action.get("id") or ""),
                sequence=int(recovery_action.get("sequence") or 0),
                event_type="action_recovery_proposed",
                status="proposed",
                capability_name=str(recovery_action.get("capability_name") or "")
                or None,
                capability_version=None,
                principal_type=run.get("principal_type"),
                principal_id=run.get("principal_id"),
                tool_id=recovery_action.get("tool_id"),
                skill_id=recovery_action.get("skill_id"),
                effect_class=recovery_action.get("effect_class"),
                trace_id=run.get("trace_id"),
                note="Recovery action proposed by operator change-plan command",
                is_policy_event=False,
                anchors={
                    "experiment_id": run.get("experiment_id"),
                    "variant_id": recovery_action.get("variant_id"),
                    "validation_job_id": recovery_action.get("validation_job_id"),
                    "hypothesis_id": recovery_action.get("hypothesis_id"),
                    "snapshot_version": recovery_action.get("snapshot_version"),
                    "metric_id": None,
                    "source_command_id": receipt.get("id"),
                    "source_action_id": action.get("id") if action else None,
                    "recovery_strategy": payload.metadata.get(
                        "recovery_strategy", "propose_next_action"
                    ),
                },
            )
            result["action"] = recovery_action
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
            actions = deps.agent_actions.list_agent_actions(
                agent_run_id=run_id,
                limit=500,
            )
            next_sequence = max(
                [int(item.get("sequence") or 0) for item in actions] or [0]
            ) + 1
            retry_count = int(action.get("retry_count") or 0) + 1
            retry_strategy = str(
                payload.metadata.get("retry_strategy") or "same_action"
            ).strip()
            allowed = [
                str(item).strip()
                for item in list(run.get("allowed_capabilities") or [])
                if str(item).strip()
            ]
            if retry_strategy == "create_recovery_action":
                capability_name = (
                    "recommend_next_action"
                    if "recommend_next_action" in allowed
                    else str(action.get("capability_name") or "")
                )
            else:
                capability_name = str(action.get("capability_name") or "")
            retry_inputs = dict(action.get("inputs") or {})
            if retry_strategy == "last_safe_checkpoint":
                retry_inputs["retry_from"] = "last_safe_checkpoint"
            if retry_strategy == "create_recovery_action":
                retry_inputs["recovery_from_action_id"] = action.get("id")
            tool_id = capability_to_tool_id(capability_name)
            retry_action = deps.agent_actions.create_agent_action(
                agent_run_id=run_id,
                sequence=next_sequence,
                status="proposed",
                capability_name=capability_name,
                capability_version=(
                    None
                    if retry_strategy == "create_recovery_action"
                    else action.get("capability_version")
                ),
                inputs=retry_inputs,
                outputs={},
                inputs_hash=_hash_payload(retry_inputs),
                outputs_hash=None,
                rationale=(
                    f"{retry_strategy} proposed from failed action {str(action.get('id') or '')[:8]}. "
                    f"{action.get('error') or action.get('rationale') or ''}"
                ).strip(),
                confidence=action.get("confidence"),
                snapshot_version=action.get("snapshot_version"),
                hypothesis_id=action.get("hypothesis_id"),
                variant_id=action.get("variant_id"),
                validation_job_id=action.get("validation_job_id"),
                tool_id=tool_id,
                skill_id=skill_id_for_tool_id(tool_id),
                effect_class=tool_effect_class(tool_id),
                retry_count=retry_count,
                dedupe_key=f"retry:{action.get('id')}:{retry_strategy}:{retry_count}",
            )
            deps.agent_events.create_agent_event(
                agent_run_id=run_id,
                action_id=str(retry_action.get("id") or ""),
                sequence=int(retry_action.get("sequence") or 0),
                event_type=(
                    "action_recovery_proposed"
                    if retry_strategy == "create_recovery_action"
                    else "action_retry_proposed"
                ),
                status="proposed",
                capability_name=str(retry_action.get("capability_name") or "") or None,
                capability_version=str(retry_action.get("capability_version") or "")
                or None,
                principal_type=run.get("principal_type"),
                principal_id=run.get("principal_id"),
                tool_id=retry_action.get("tool_id"),
                skill_id=retry_action.get("skill_id"),
                effect_class=retry_action.get("effect_class"),
                trace_id=run.get("trace_id"),
                note="Retry action proposed by operator chat",
                is_policy_event=False,
                anchors={
                    "experiment_id": run.get("experiment_id"),
                    "variant_id": retry_action.get("variant_id"),
                    "validation_job_id": retry_action.get("validation_job_id"),
                    "hypothesis_id": retry_action.get("hypothesis_id"),
                    "snapshot_version": retry_action.get("snapshot_version"),
                    "metric_id": None,
                    "original_action_id": action.get("id"),
                    "retry_count": retry_count,
                    "retry_strategy": retry_strategy,
                },
            )
            result["action"] = retry_action
        elif command_type in {"approve", "reject"}:
            if not action:
                raise HTTPException(status_code=400, detail="Action id is required")
            status = "rejected" if command_type == "reject" else "approved"
            updated = deps.agent_actions.update_agent_action_status(
                action_id=str(action.get("id")),
                status=status,
            )
            current = updated or action
            deps.agent_events.create_agent_event(
                agent_run_id=run_id,
                action_id=str(current.get("id") or ""),
                sequence=int(current.get("sequence") or 0),
                event_type=(
                    f"action_{status}"
                ),
                status=status,
                capability_name=str(current.get("capability_name") or "") or None,
                capability_version=str(current.get("capability_version") or "") or None,
                principal_type=run.get("principal_type"),
                principal_id=run.get("principal_id"),
                tool_id=current.get("tool_id")
                or capability_to_tool_id(current.get("capability_name")),
                skill_id=current.get("skill_id")
                or skill_id_for_tool_id(
                    current.get("tool_id")
                    or capability_to_tool_id(current.get("capability_name"))
                ),
                effect_class=current.get("effect_class")
                or tool_effect_class(
                    current.get("tool_id")
                    or capability_to_tool_id(current.get("capability_name"))
                ),
                trace_id=run.get("trace_id"),
                note=f"Action {command_type} by operator chat",
                is_policy_event=False,
                anchors={
                    "experiment_id": run.get("experiment_id"),
                    "variant_id": current.get("variant_id"),
                    "validation_job_id": current.get("validation_job_id"),
                    "hypothesis_id": current.get("hypothesis_id"),
                    "snapshot_version": current.get("snapshot_version"),
                    "metric_id": None,
                },
            )
            result["action"] = updated or action
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
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=scoped_client_id
    )
    if not action:
        raise HTTPException(status_code=404, detail="Agent action not found")
    decision = str(payload.decision or "").strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Invalid decision")
    updated = deps.agent_actions.update_agent_action_status(
        action_id=action_id,
        status="approved" if decision == "approve" else "rejected",
    )
    current = updated or action
    run_row = deps.agent_runs.get_agent_run(
        run_id=str(current.get("agent_run_id") or ""), client_id=scoped_client_id
    )
    deps.agent_events.create_agent_event(
        agent_run_id=str(current.get("agent_run_id") or ""),
        action_id=str(current.get("id") or action_id),
        sequence=int(current.get("sequence") or 0),
        event_type=f"action_{'approved' if decision == 'approve' else 'rejected'}",
        status="approved" if decision == "approve" else "rejected",
        capability_name=str(current.get("capability_name") or "") or None,
        capability_version=str(current.get("capability_version") or "") or None,
        principal_type=run_row.get("principal_type") if run_row else "human",
        principal_id=run_row.get("principal_id") if run_row else (payload.user_id or None),
        tool_id=current.get("tool_id") or capability_to_tool_id(current.get("capability_name")),
        skill_id=current.get("skill_id")
        or skill_id_for_tool_id(
            current.get("tool_id") or capability_to_tool_id(current.get("capability_name"))
        ),
        effect_class=current.get("effect_class")
        or tool_effect_class(
            current.get("tool_id") or capability_to_tool_id(current.get("capability_name"))
        ),
        trace_id=run_row.get("trace_id") if run_row else None,
        note=f"Action {decision} by operator",
        is_policy_event=False,
        anchors={
            "experiment_id": run_row.get("experiment_id") if run_row else None,
            "variant_id": current.get("variant_id"),
            "validation_job_id": current.get("validation_job_id"),
            "hypothesis_id": current.get("hypothesis_id"),
            "snapshot_version": current.get("snapshot_version"),
            "metric_id": None,
        },
    )
    return {"action": updated or action}
