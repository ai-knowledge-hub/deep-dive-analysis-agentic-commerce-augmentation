from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.agent_registry_runtime import registry_payload_and_fingerprint
from api.utils.principals import PrincipalContext, resolve_principal_context
from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    list_skill_specs,
    select_skill_for_tool_id,
)
from application.services.agent_runtime.registry import get_tool_spec
from application.services.agent_runtime.runs import create_agent_run_with_initial_plan
from infrastructure.db.agent.agent_registry import ensure_agent_registry_version
from infrastructure.db.agent.external_agent_jobs import (
    create_external_agent_job,
    get_external_agent_job,
    get_external_agent_job_by_idempotency_key,
    update_external_agent_job_status,
)

router = APIRouter(prefix="/external-agent/jobs", tags=["external-agent-jobs"])


def _deps() -> AppDeps:
    return default_deps()


class ExternalAgentJobCreateRequest(BaseModel):
    idempotency_key: str = Field(..., min_length=1)
    brand_id: Optional[str] = None
    product_id: Optional[str] = None
    experiment_id: Optional[str] = None
    objective: Dict[str, Any] = Field(default_factory=dict)
    skill_id: Optional[str] = None
    tool_id: Optional[str] = None
    capability_name: Optional[str] = None
    allowed_capabilities: List[str] = Field(default_factory=list)
    capability_versions: Dict[str, Any] = Field(default_factory=dict)
    budgets: Dict[str, Any] = Field(default_factory=dict)
    approval_policy: Dict[str, Any] = Field(default_factory=dict)
    harness_id: Optional[str] = None
    policy_profile_id: Optional[str] = None
    requires_approval: bool = True
    run_mode: str = "plan_only"
    state: str = "battery_ready"


class ExternalAgentJobResponse(BaseModel):
    job: Dict[str, Any]
    run: Dict[str, Any]
    idempotent_replay: bool = False


@router.post("")
def create_external_agent_job_route(
    payload: ExternalAgentJobCreateRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(principal, "external_agent_jobs:write", "agent_runs:write")
    resolved = _resolve_requested_runtime_contract(payload)
    _require_requested_skill_tool_scopes(
        principal,
        skill_id=resolved["skill_id"],
        tool_id=resolved["tool_id"],
    )
    request_hash = _request_hash(payload.model_dump(mode="json"))
    existing = get_external_agent_job_by_idempotency_key(
        client_id=principal.client_id,
        principal_id=principal.principal_id,
        idempotency_key=payload.idempotency_key,
    )
    if existing:
        if existing["request_hash"] != request_hash:
            raise HTTPException(
                status_code=409,
                detail="idempotency_key already used with a different request payload",
            )
        run = deps.agent_runs.get_agent_run(
            run_id=existing["run_id"], client_id=principal.client_id
        )
        if not run:
            raise HTTPException(status_code=409, detail="idempotent job run is missing")
        job = _job_status_payload(job=existing, run=run)
        return ExternalAgentJobResponse(job=job, run=run, idempotent_replay=True)

    registry_payload, active_registry_fingerprint = registry_payload_and_fingerprint()
    ensure_agent_registry_version(
        registry_version=str(registry_payload["registry_version"]),
        registry_fingerprint=active_registry_fingerprint,
        hash_algorithm="sha256",
        payload=registry_payload,
    )
    run = create_agent_run_with_initial_plan(
        deps=deps,
        client_id=principal.client_id,
        brand_id=payload.brand_id,
        product_id=payload.product_id,
        experiment_id=payload.experiment_id,
        objective={
            **(payload.objective or {}),
            "external_job": True,
            "requested_skill_id": resolved["skill_id"],
            "requested_tool_id": resolved["tool_id"],
        },
        allowed_capabilities=resolved["allowed_capabilities"],
        capability_versions=payload.capability_versions,
        budgets=payload.budgets,
        approval_policy=payload.approval_policy,
        requires_approval=payload.requires_approval,
        run_mode=payload.run_mode,
        state=payload.state,
        status="planned",
        principal_type=principal.principal_type,
        principal_id=principal.principal_id,
        agent_profile_id=principal.agent_profile_id,
        harness_id=payload.harness_id,
        policy_profile_id=payload.policy_profile_id,
        idempotency_key=payload.idempotency_key,
        registry_payload=registry_payload,
        active_registry_fingerprint=active_registry_fingerprint,
    )
    response = {
        "job_id": None,
        "run_id": run["id"],
        "status": _job_status_from_run(run),
        "trace_id": run.get("trace_id"),
        "requested_skill_id": resolved["skill_id"],
        "requested_tool_id": resolved["tool_id"],
    }
    created = create_external_agent_job(
        client_id=principal.client_id,
        principal_id=principal.principal_id,
        agent_profile_id=principal.agent_profile_id,
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
        run_id=run["id"],
        requested_skill_id=resolved["skill_id"],
        requested_tool_id=resolved["tool_id"],
        status=response["status"],
        trace_id=run.get("trace_id"),
        request=payload.model_dump(mode="json"),
        response=response,
    )
    response["job_id"] = created["id"]
    created = update_external_agent_job_status(
        job_id=created["id"], status=response["status"], response=response
    ) or created
    return ExternalAgentJobResponse(job=_job_status_payload(job=created, run=run), run=run)


@router.get("/{job_id}")
def get_external_agent_job_route(
    job_id: str,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(
        principal,
        "external_agent_jobs:read",
        "external_agent_jobs:write",
        "agent_runs:read",
        "agent_runs:write",
    )
    job = get_external_agent_job(
        job_id=job_id, client_id=principal.client_id, principal_id=principal.principal_id
    )
    if not job:
        raise HTTPException(status_code=404, detail="External agent job not found")
    run = deps.agent_runs.get_agent_run(run_id=job["run_id"], client_id=principal.client_id)
    if not run:
        raise HTTPException(status_code=404, detail="External agent job run not found")
    status = _job_status_from_run(run)
    if status != job["status"]:
        job = update_external_agent_job_status(
            job_id=job["id"],
            status=status,
            response={**(job.get("response") or {}), "status": status},
        ) or job
    return ExternalAgentJobResponse(job=_job_status_payload(job=job, run=run), run=run)


def _require_external_agent_principal(*, request: Request) -> PrincipalContext:
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    scheme, _, token = str(auth_header or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="External agent jobs require an external_agent bearer token",
        )
    principal = resolve_principal_context(
        request=request,
        client_id=None,
        user_id=None,
        principal_type="external_agent",
        principal_id=None,
        agent_profile_id=None,
    )
    if principal.auth_method != "bearer_token" or principal.principal_type != "external_agent":
        raise HTTPException(
            status_code=401,
            detail="External agent jobs require an external_agent bearer token",
        )
    return principal


def _resolve_requested_runtime_contract(
    payload: ExternalAgentJobCreateRequest,
) -> Dict[str, Any]:
    capability_name = str(payload.capability_name or "").strip() or None
    tool_id = str(payload.tool_id or "").strip() or None
    if capability_name and not tool_id:
        tool_id = capability_to_tool_id(capability_name)
    tool = get_tool_spec(tool_id) if tool_id else None
    if tool_id and not tool:
        raise HTTPException(status_code=400, detail=f"Unsupported tool_id: {tool_id}")
    if tool and not capability_name:
        capability_name = tool.capability_name

    skill_id = str(payload.skill_id or "").strip() or None
    if skill_id and skill_id not in {skill.id for skill in list_skill_specs()}:
        raise HTTPException(status_code=400, detail=f"Unsupported skill_id: {skill_id}")
    if tool_id:
        selected = select_skill_for_tool_id(tool_id, preferred_skill_id=skill_id)
        if skill_id and (not selected or selected.id != skill_id):
            raise HTTPException(
                status_code=400,
                detail=f"Skill '{skill_id}' cannot use tool '{tool_id}'",
            )
        skill_id = selected.id if selected else skill_id

    allowed_capabilities = [
        str(item).strip() for item in payload.allowed_capabilities if str(item).strip()
    ]
    if capability_name and capability_name not in allowed_capabilities:
        allowed_capabilities = [capability_name, *allowed_capabilities]
    if not allowed_capabilities:
        raise HTTPException(
            status_code=400,
            detail="External agent job requires a tool_id, capability_name, or allowed_capabilities",
        )
    return {
        "skill_id": skill_id,
        "tool_id": tool_id,
        "allowed_capabilities": allowed_capabilities,
    }


def _require_requested_skill_tool_scopes(
    principal: PrincipalContext, *, skill_id: Optional[str], tool_id: Optional[str]
) -> None:
    if tool_id and not _has_any_scope(principal, f"tool:{tool_id}", "tools:*"):
        raise HTTPException(status_code=403, detail=f"Missing scope for tool '{tool_id}'")
    if skill_id and not _has_any_scope(principal, f"skill:{skill_id}", "skills:*"):
        raise HTTPException(status_code=403, detail=f"Missing scope for skill '{skill_id}'")


def _require_any_scope(principal: PrincipalContext, *required: str) -> None:
    if not _has_any_scope(principal, *required):
        raise HTTPException(status_code=403, detail="Missing required external agent scope")


def _has_any_scope(principal: PrincipalContext, *required: str) -> bool:
    scopes = set(principal.scopes or ())
    return "*" in scopes or any(scope in scopes for scope in required)


def _request_hash(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _job_status_from_run(run: Dict[str, Any]) -> str:
    status = str(run.get("status") or "planned")
    if status in {"completed", "failed", "cancelled"}:
        return status
    if status in {"running", "executing"}:
        return "running"
    return "accepted"


def _job_status_payload(*, job: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": job["id"],
        "client_id": job["client_id"],
        "principal_id": job["principal_id"],
        "agent_profile_id": job.get("agent_profile_id"),
        "idempotency_key": job["idempotency_key"],
        "run_id": job["run_id"],
        "status": _job_status_from_run(run),
        "trace_id": job.get("trace_id") or run.get("trace_id"),
        "requested_skill_id": job.get("requested_skill_id"),
        "requested_tool_id": job.get("requested_tool_id"),
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


__all__ = ["router"]
