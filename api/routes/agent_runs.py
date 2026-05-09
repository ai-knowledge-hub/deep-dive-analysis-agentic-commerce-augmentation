from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request

from api.composition import default_deps
from api.routes.agent_run_models import (
    AgentRunCreateRequest,
    AgentRunDetailResponse,
    AgentRunEventListResponse,
    AgentRunListResponse,
)
from api.utils.agent_registry_runtime import registry_payload_and_fingerprint
from api.utils.agent_run_authorization import (
    filter_agent_runs_for_principal,
    require_agent_run_control_access,
    require_agent_run_create_principal_access,
    require_agent_run_list_access,
)
from api.utils.principals import resolve_principal_context
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.events import list_agent_run_events_page
from application.services.agent_runtime import registry as agent_registry
from application.services.agent_runtime.runs import (
    AgentRunPlanError,
    create_agent_run_with_initial_plan,
)
from infrastructure.db.agent.agent_registry import ensure_agent_registry_version


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])


def _deps() -> AppDeps:
    return default_deps()


def registry_contract_payload(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    return agent_registry.registry_contract_payload(*args, **kwargs)


def registry_fingerprint(*args: Any, **kwargs: Any) -> str:
    return agent_registry.registry_fingerprint(*args, **kwargs)


def _require_scoped_run(
    *, deps: AppDeps, run_id: str, client_id: str
) -> Dict[str, Any]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return run


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
    require_agent_run_create_principal_access(
        principal=principal,
        requested_principal_type=payload.principal_type,
        requested_principal_id=payload.principal_id,
        requested_agent_profile_id=payload.agent_profile_id,
    )
    registry_payload, active_registry_fingerprint = registry_payload_and_fingerprint()
    ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=active_registry_fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    try:
        run = create_agent_run_with_initial_plan(
            deps=deps,
            client_id=principal.client_id,
            brand_id=payload.brand_id,
            product_id=payload.product_id,
            experiment_id=payload.experiment_id,
            objective=payload.objective,
            allowed_capabilities=payload.allowed_capabilities,
            capability_versions=payload.capability_versions,
            budgets=payload.budgets,
            approval_policy=payload.approval_policy,
            requires_approval=payload.requires_approval,
            run_mode=payload.run_mode,
            state=payload.state,
            status=payload.status,
            principal_type=principal.principal_type,
            principal_id=principal.principal_id,
            agent_profile_id=principal.agent_profile_id,
            harness_id=payload.harness_id,
            policy_profile_id=payload.policy_profile_id,
            idempotency_key=payload.idempotency_key,
            registry_payload=registry_payload,
            active_registry_fingerprint=active_registry_fingerprint,
        )
    except AgentRunPlanError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run": run}


@router.get("")
def list_agent_runs(
    request: Request,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    deps: AppDeps = Depends(_deps),
) -> AgentRunListResponse:
    resolved = require_client_id(client_id, user_id)
    principal = require_agent_run_list_access(
        request=request,
        client_id=resolved,
        user_id=user_id,
        required_scope="agent_runs:read",
    )
    runs = deps.agent_runs.list_agent_runs(
        client_id=resolved,
        experiment_id=experiment_id,
        product_id=product_id,
        status=status,
        limit=limit,
    )
    return AgentRunListResponse(
        runs=filter_agent_runs_for_principal(runs=runs, principal=principal)
    )


@router.get("/{run_id}")
def get_agent_run(
    run_id: str,
    request: Request,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    limit: int = 200,
    deps: AppDeps = Depends(_deps),
) -> AgentRunDetailResponse:
    scoped_client_id = require_client_id(client_id, user_id)
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=user_id,
        required_scope="agent_runs:read",
    )
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=limit)
    return AgentRunDetailResponse(run=run, actions=actions)


@router.get("/{run_id}/events")
def get_agent_run_events(
    run_id: str,
    request: Request,
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
    run = _require_scoped_run(deps=deps, run_id=run_id, client_id=scoped_client_id)
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=user_id,
        required_scope="agent_runs:read",
    )
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
