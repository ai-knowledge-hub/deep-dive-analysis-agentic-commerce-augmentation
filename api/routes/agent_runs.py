from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.routes.agent_runs_commands import (
    _capability_rollback_guidance,
    _capability_side_effects,
    _compensating_actions_for_capability,
    _hash_payload,
)
from api.utils.principals import resolve_principal_context
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    new_trace_id,
    policy_profile_for_run_mode,
    skill_id_for_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.events import list_agent_run_events_page
from application.services.agent_runtime.planner import build_initial_plan
from application.services.agent_runtime.registry import (
    default_tool_ownership_records,
    registry_contract_payload,
    registry_fingerprint,
    version_context_for_capability,
)
from infrastructure.db.agent.agent_registry import (
    ensure_agent_registry_tool_ownership,
    ensure_agent_registry_version,
    list_agent_registry_tool_ownership,
)


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def _deps() -> AppDeps:
    return default_deps()


def _require_scoped_run(*, deps: AppDeps, run_id: str, client_id: str) -> Dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


def _registry_ownership() -> List[Dict[str, Any]]:
    ownership = ensure_agent_registry_tool_ownership(
        ownership=default_tool_ownership_records(),
        source="registry_default",
    )
    return ownership or list_agent_registry_tool_ownership()


def _registry_payload_and_fingerprint() -> tuple[Dict[str, Any], str]:
    ownership = _registry_ownership()
    try:
        registry_payload = registry_contract_payload(ownership_by_tool=ownership)
    except TypeError:
        registry_payload = registry_contract_payload()
    try:
        fingerprint = registry_fingerprint(ownership_by_tool=ownership)
    except TypeError:
        fingerprint = registry_fingerprint()
    return registry_payload, fingerprint


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
    registry_payload, active_registry_fingerprint = _registry_payload_and_fingerprint()
    ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=active_registry_fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
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
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=active_registry_fingerprint,
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
        effect_class = tool_effect_class(tool_id)
        version_context = version_context_for_capability(
            action.capability_name,
            tool_id=tool_id,
            skill_id=skill_id,
            registry_version_override=str(registry_payload["registry_version"]),
            registry_fingerprint_override=active_registry_fingerprint,
        )
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
            registry_version=version_context["registry_version"],
            registry_fingerprint=version_context["registry_fingerprint"],
            tool_version=version_context["tool_version"],
            skill_version=version_context["skill_version"],
            effect_class=effect_class,
            side_effects=_capability_side_effects(action.capability_name),
            rollback_guidance=_capability_rollback_guidance(
                action.capability_name, effect_class
            ),
            compensating_actions=_compensating_actions_for_capability(
                capability_name=action.capability_name,
                effect_class=effect_class,
                allowed_capabilities=payload.allowed_capabilities or [],
            ),
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
