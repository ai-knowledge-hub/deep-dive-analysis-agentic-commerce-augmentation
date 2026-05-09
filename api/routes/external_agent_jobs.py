from __future__ import annotations

import hashlib
import base64
import hmac
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.utils.agent_registry_runtime import registry_payload_and_fingerprint
from api.utils.principals import PrincipalContext, resolve_principal_context
from application.ports.deps import AppDeps
from application.services.agent_runtime.events import list_agent_run_events_page
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    list_skill_specs,
    select_skill_for_tool_id,
)
from application.services.agent_runtime.registry import get_tool_spec
from application.services.agent_runtime.runs import (
    AgentRunPlanError,
    create_agent_run_with_initial_plan,
)
from infrastructure.db.agent.agent_registry import ensure_agent_registry_version
from infrastructure.db.agent.external_agent_jobs import (
    create_external_agent_job_receipt,
    create_external_agent_job,
    delete_external_agent_job_idempotency_reservation,
    get_external_agent_job,
    get_external_agent_job_by_idempotency_key,
    get_external_agent_job_idempotency_reservation,
    get_external_agent_job_receipt_for_context_hash,
    list_external_agent_job_receipts,
    reserve_external_agent_job_idempotency,
    update_external_agent_job_receipt,
    update_external_agent_job_status,
)
from shared.config.env import get_settings

router = APIRouter(prefix="/external-agent/jobs", tags=["external-agent-jobs"])

_POLL_RETRY_AFTER_SECONDS = 3
_POLL_INTERVAL_SECONDS = 3
_TERMINAL_JOB_STATUSES = {"completed", "failed", "canceled"}
_ACTION_EVIDENCE_LIMIT = 500
_EVENT_EVIDENCE_LIMIT = 2000


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
    plan_mode: Optional[str] = None
    state: str = "battery_ready"


class ExternalAgentJobResponse(BaseModel):
    job: Dict[str, Any]
    run: Dict[str, Any]
    idempotent_replay: bool = False


class ExternalAgentJobReceiptResponse(BaseModel):
    receipt: Dict[str, Any]


class ExternalAgentJobReceiptVerifyRequest(BaseModel):
    receipt: Dict[str, Any]


class ExternalAgentJobEventListResponse(BaseModel):
    events: List[Dict[str, Any]]
    page: Dict[str, Any]


class ExternalAgentJobReceiptListResponse(BaseModel):
    receipts: List[Dict[str, Any]]


class ExternalAgentJobActivityResponse(BaseModel):
    job: Dict[str, Any]
    summary: Dict[str, Any]
    items: List[Dict[str, Any]]
    event_page: Dict[str, Any]
    page: Dict[str, Any]


@router.post("")
def create_external_agent_job_route(
    payload: ExternalAgentJobCreateRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(principal, "external_agent_jobs:write", "agent_runs:write")
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

    resolved = _resolve_requested_runtime_contract(payload)
    _require_requested_skill_tool_scopes(
        principal,
        skill_ids=resolved["scope_skill_ids"],
        tool_ids=resolved["scope_tool_ids"],
    )
    if not reserve_external_agent_job_idempotency(
        client_id=principal.client_id,
        principal_id=principal.principal_id,
        idempotency_key=payload.idempotency_key,
        request_hash=request_hash,
    ):
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
        reservation = get_external_agent_job_idempotency_reservation(
            client_id=principal.client_id,
            principal_id=principal.principal_id,
            idempotency_key=payload.idempotency_key,
        )
        if reservation and reservation.get("request_hash") != request_hash:
            raise HTTPException(
                status_code=409,
                detail="idempotency_key already reserved with a different request payload",
            )
        raise HTTPException(
            status_code=409,
            detail="idempotent job creation is already in progress; retry with the same idempotency_key",
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
            objective={
                **(payload.objective or {}),
                "external_job": True,
                "requested_skill_id": resolved["skill_id"],
                "requested_tool_id": resolved["tool_id"],
                "plan_mode": resolved["plan_mode"],
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
            preferred_skill_id=resolved["skill_id"],
        )
    except AgentRunPlanError as exc:
        delete_external_agent_job_idempotency_reservation(
            client_id=principal.client_id,
            principal_id=principal.principal_id,
            idempotency_key=payload.idempotency_key,
        )
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    response = {
        "job_id": None,
        "run_id": run["id"],
        "status": _job_status_from_run(run),
        "trace_id": run.get("trace_id"),
        "requested_skill_id": resolved["skill_id"],
        "requested_tool_id": resolved["tool_id"],
    }
    try:
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
    except Exception:
        deps.agent_runs.delete_agent_run(run_id=run["id"], client_id=principal.client_id)
        delete_external_agent_job_idempotency_reservation(
            client_id=principal.client_id,
            principal_id=principal.principal_id,
            idempotency_key=payload.idempotency_key,
        )
        raise
    if created["request_hash"] != request_hash:
        deps.agent_runs.delete_agent_run(run_id=run["id"], client_id=principal.client_id)
        raise HTTPException(
            status_code=409,
            detail="idempotency_key already used with a different request payload",
        )
    if created["run_id"] != run["id"]:
        deps.agent_runs.delete_agent_run(run_id=run["id"], client_id=principal.client_id)
        existing_run = deps.agent_runs.get_agent_run(
            run_id=created["run_id"], client_id=principal.client_id
        )
        if not existing_run:
            raise HTTPException(status_code=409, detail="idempotent job run is missing")
        job = _job_status_payload(job=created, run=existing_run)
        return ExternalAgentJobResponse(job=job, run=existing_run, idempotent_replay=True)
    response["job_id"] = created["id"]
    created = update_external_agent_job_status(
        job_id=created["id"], status=response["status"], response=response
    ) or created
    return ExternalAgentJobResponse(job=_job_status_payload(job=created, run=run), run=run)


@router.get("/{job_id}")
def get_external_agent_job_route(
    job_id: str,
    request: Request,
    response: Response,
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
    _set_external_agent_poll_headers(response)
    return ExternalAgentJobResponse(job=_job_status_payload(job=job, run=run), run=run)


@router.get("/{job_id}/receipt")
def get_external_agent_job_receipt_route(
    job_id: str,
    request: Request,
    response: Response,
    refresh: bool = False,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobReceiptResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(
        principal,
        "external_agent_jobs:read",
        "external_agent_jobs:write",
        "agent_runs:read",
        "agent_runs:write",
    )
    job, run = _require_scoped_job_and_run(
        deps=deps, job_id=job_id, principal=principal
    )
    current_status = _job_status_from_run(run)
    if refresh or current_status in _TERMINAL_JOB_STATUSES:
        receipt = _ensure_external_agent_job_receipt(deps=deps, job=job, run=run)
    else:
        receipt = _stored_external_agent_job_receipt(job=job, run=run)
        if not receipt:
            raise HTTPException(
                status_code=404,
                detail="No stored receipt exists for this job status; call with refresh=true to mint one.",
            )
    _set_external_agent_poll_headers(response)
    return ExternalAgentJobReceiptResponse(receipt=receipt)


@router.post("/{job_id}/receipt/verify")
def verify_external_agent_job_receipt_route(
    job_id: str,
    payload: ExternalAgentJobReceiptVerifyRequest,
    request: Request,
    response: Response,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(
        principal,
        "external_agent_jobs:read",
        "external_agent_jobs:write",
        "agent_runs:read",
        "agent_runs:write",
    )
    job, _run = _require_scoped_job_and_run(
        deps=deps, job_id=job_id, principal=principal
    )
    receipt = dict(payload.receipt or {})
    decoded_payload, valid_signature = _decode_external_agent_job_receipt_signature(
        str(receipt.get("signature") or "")
    )
    unsigned_receipt = {
        key: value
        for key, value in receipt.items()
        if key not in {"signature", "signature_algorithm"}
    }
    valid_payload = bool(valid_signature and decoded_payload == unsigned_receipt)
    valid_scope = bool(
        decoded_payload.get("job_id") == job["id"]
        and decoded_payload.get("run_id") == job["run_id"]
        and decoded_payload.get("client_id") == principal.client_id
        and decoded_payload.get("principal_id") == principal.principal_id
    )
    blockers: List[str] = []
    if not valid_signature:
        blockers.append("Receipt signature is invalid.")
    if valid_signature and not valid_payload:
        blockers.append("Receipt payload does not match the signed payload.")
    if valid_signature and not valid_scope:
        blockers.append("Receipt does not belong to the scoped external-agent job.")
    _set_external_agent_poll_headers(response)
    return {
        "valid": not blockers,
        "valid_signature": valid_signature,
        "valid_payload": valid_payload,
        "valid_scope": valid_scope,
        "key_id": decoded_payload.get("key_id") or receipt.get("key_id"),
        "signature_algorithm": receipt.get("signature_algorithm"),
        "receipt_payload": decoded_payload,
        "blockers": blockers,
    }


@router.get("/{job_id}/receipts")
def list_external_agent_job_receipts_route(
    job_id: str,
    request: Request,
    response: Response,
    limit: int = 50,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobReceiptListResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(
        principal,
        "external_agent_jobs:read",
        "external_agent_jobs:write",
        "agent_runs:read",
        "agent_runs:write",
    )
    _job, _run = _require_scoped_job_and_run(
        deps=deps, job_id=job_id, principal=principal
    )
    rows = list_external_agent_job_receipts(
        job_id=job_id,
        client_id=principal.client_id,
        principal_id=principal.principal_id,
        limit=limit,
    )
    receipts = sorted(
        [
            {
                **(row.get("payload") or {}),
                "signature": row.get("signature"),
                "signature_algorithm": row.get("signature_algorithm"),
            }
            for row in rows
        ],
        key=lambda item: str(item.get("issued_at") or item.get("created_at") or ""),
        reverse=True,
    )
    _set_external_agent_poll_headers(response)
    return ExternalAgentJobReceiptListResponse(receipts=receipts)


@router.get("/{job_id}/activity")
def get_external_agent_job_activity_route(
    job_id: str,
    request: Request,
    response: Response,
    limit: int = 100,
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
) -> ExternalAgentJobActivityResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(
        principal,
        "external_agent_jobs:read",
        "external_agent_jobs:write",
        "agent_runs:read",
        "agent_runs:write",
    )
    job, run = _require_scoped_job_and_run(
        deps=deps, job_id=job_id, principal=principal
    )
    receipt_rows = list_external_agent_job_receipts(
        job_id=job_id,
        client_id=principal.client_id,
        principal_id=principal.principal_id,
        limit=limit,
    )
    try:
        page = list_agent_run_events_page(
            deps=deps,
            run_id=job["run_id"],
            client_id=principal.client_id,
            limit=max(1, min(int(limit), 2000)),
            event_type=event_type or "all",
            status=status,
            capability_name=capability_name,
            since=since,
            until=until,
            before=before,
            after=after,
            event_id=event_id,
            around=max(1, min(int(around), 2000)),
        ).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    items = _external_agent_activity_items(
        job=job,
        run=run,
        receipts=receipt_rows,
        events=page["events"],
    )
    _set_external_agent_poll_headers(response)
    return ExternalAgentJobActivityResponse(
        job=_job_status_payload(job=job, run=run),
        summary={
            "status": _job_status_from_run(run),
            "run_status": run.get("status"),
            "run_state": run.get("state"),
            "run_id": run.get("id"),
            "trace_id": job.get("trace_id") or run.get("trace_id"),
            "receipt_count": len(receipt_rows),
            "event_count": len(page["events"]),
            "page_scope": "run_events",
        },
        items=items,
        event_page=page["page"],
        page=page["page"],
    )


@router.get("/{job_id}/events")
def get_external_agent_job_events_route(
    job_id: str,
    request: Request,
    response: Response,
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
) -> ExternalAgentJobEventListResponse:
    principal = _require_external_agent_principal(request=request)
    _require_any_scope(
        principal,
        "external_agent_jobs:read",
        "external_agent_jobs:write",
        "agent_runs:read",
        "agent_runs:write",
    )
    job, run = _require_scoped_job_and_run(
        deps=deps, job_id=job_id, principal=principal
    )
    try:
        page = list_agent_run_events_page(
            deps=deps,
            run_id=job["run_id"],
            client_id=principal.client_id,
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
    _sync_job_status_from_run(job=job, run=run)
    _set_external_agent_poll_headers(response)
    return ExternalAgentJobEventListResponse(
        events=payload["events"], page=payload["page"]
    )


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


def _require_scoped_job_and_run(
    *, deps: AppDeps, job_id: str, principal: PrincipalContext
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    job = get_external_agent_job(
        job_id=job_id,
        client_id=principal.client_id,
        principal_id=principal.principal_id,
    )
    if not job:
        raise HTTPException(status_code=404, detail="External agent job not found")
    run = deps.agent_runs.get_agent_run(run_id=job["run_id"], client_id=principal.client_id)
    if not run:
        raise HTTPException(status_code=404, detail="External agent job run not found")
    job = _sync_job_status_from_run(job=job, run=run)
    return job, run


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
    plan_mode = str(
        payload.plan_mode or ("single_tool" if capability_name else "workflow")
    ).strip().lower()
    if plan_mode not in {"single_tool", "workflow"}:
        raise HTTPException(
            status_code=400,
            detail="plan_mode must be 'single_tool' or 'workflow'",
        )
    if plan_mode == "single_tool":
        if not capability_name:
            raise HTTPException(
                status_code=400,
                detail="single_tool plan_mode requires a tool_id or capability_name",
            )
        allowed_capabilities = [capability_name]
    return {
        "skill_id": skill_id,
        "tool_id": tool_id,
        "allowed_capabilities": allowed_capabilities,
        "plan_mode": plan_mode,
        "scope_tool_ids": _tool_ids_for_capabilities(allowed_capabilities),
        "scope_skill_ids": _scope_skill_ids_for_capabilities(
            allowed_capabilities=allowed_capabilities,
            requested_capability_name=capability_name,
            requested_skill_id=skill_id,
        ),
    }


def _require_requested_skill_tool_scopes(
    principal: PrincipalContext, *, skill_ids: List[str], tool_ids: List[str]
) -> None:
    for tool_id in tool_ids:
        if not _has_any_scope(principal, f"tool:{tool_id}", "tools:*"):
            raise HTTPException(
                status_code=403, detail=f"Missing scope for tool '{tool_id}'"
            )
    for skill_id in skill_ids:
        if not _has_any_scope(principal, f"skill:{skill_id}", "skills:*"):
            raise HTTPException(
                status_code=403, detail=f"Missing scope for skill '{skill_id}'"
            )


def _tool_ids_for_capabilities(capability_names: List[str]) -> List[str]:
    tool_ids: List[str] = []
    for capability_name in capability_names:
        tool_id = capability_to_tool_id(capability_name)
        if not tool_id or not get_tool_spec(tool_id):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported capability_name: {capability_name}",
            )
        if tool_id not in tool_ids:
            tool_ids.append(tool_id)
    return tool_ids


def _skill_ids_for_capabilities(capability_names: List[str]) -> List[str]:
    skill_ids: List[str] = []
    for tool_id in _tool_ids_for_capabilities(capability_names):
        selected = select_skill_for_tool_id(tool_id)
        if selected and selected.id not in skill_ids:
            skill_ids.append(selected.id)
    return skill_ids


def _scope_skill_ids_for_capabilities(
    *,
    allowed_capabilities: List[str],
    requested_capability_name: str | None,
    requested_skill_id: str | None,
) -> List[str]:
    skill_ids: List[str] = []
    requested_capability = str(requested_capability_name or "").strip()
    for capability_name in allowed_capabilities:
        if (
            requested_skill_id
            and requested_capability
            and capability_name == requested_capability
        ):
            selected_id = requested_skill_id
        else:
            tool_id = capability_to_tool_id(capability_name)
            selected = select_skill_for_tool_id(tool_id)
            selected_id = selected.id if selected else None
        if selected_id and selected_id not in skill_ids:
            skill_ids.append(selected_id)
    return skill_ids


def _dedupe_ids(items: List[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


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
    status = str(run.get("status") or "planned").strip().lower()
    if status in {"completed", "failed", "paused"}:
        return status
    if status in {"canceled", "cancelled"}:
        return "canceled"
    if status in {"running", "executing"}:
        return "running"
    return "accepted"


def _job_status_payload(*, job: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    status = _job_status_from_run(run)
    receipt_payload = job.get("receipt_payload") or {}
    receipt_matches_status = receipt_payload.get("status") == status
    return {
        "id": job["id"],
        "client_id": job["client_id"],
        "principal_id": job["principal_id"],
        "agent_profile_id": job.get("agent_profile_id"),
        "idempotency_key": job["idempotency_key"],
        "run_id": job["run_id"],
        "status": status,
        "run_status": run.get("status"),
        "run_state": run.get("state"),
        "trace_id": job.get("trace_id") or run.get("trace_id"),
        "requested_skill_id": job.get("requested_skill_id"),
        "requested_tool_id": job.get("requested_tool_id"),
        "receipt_id": job.get("receipt_id") if receipt_matches_status else None,
        "receipt_type": job.get("receipt_type") if receipt_matches_status else None,
        "receipt_signature_algorithm": job.get("receipt_signature_algorithm")
        if receipt_matches_status
        else None,
        "created_at": job.get("created_at"),
        "updated_at": job.get("updated_at"),
    }


def _sync_job_status_from_run(*, job: Dict[str, Any], run: Dict[str, Any]) -> Dict[str, Any]:
    status = _job_status_from_run(run)
    if status == job.get("status"):
        return job
    return update_external_agent_job_status(
        job_id=job["id"],
        status=status,
        response={**(job.get("response") or {}), "status": status},
    ) or job


def _ensure_external_agent_job_receipt(
    *, deps: AppDeps, job: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any]:
    current_status = _job_status_from_run(run)
    evidence = _job_evidence_summary(deps=deps, run=run)
    context_hash = _receipt_context_hash(
        job=job, run=run, current_status=current_status, evidence=evidence
    )
    if (
        job.get("receipt_id")
        and job.get("receipt_signature")
        and (job.get("receipt_payload") or {}).get("status") == current_status
        and (job.get("receipt_payload") or {}).get("receipt_context_hash")
        == context_hash
    ):
        return {
            **(job.get("receipt_payload") or {}),
            "signature": job.get("receipt_signature"),
            "signature_algorithm": job.get("receipt_signature_algorithm"),
        }
    receipt_payload = {
        "receipt_id": str(uuid.uuid4()),
        "receipt_type": f"external_agent_job_{current_status}",
        "job_id": job["id"],
        "run_id": job["run_id"],
        "client_id": job["client_id"],
        "principal_id": job["principal_id"],
        "agent_profile_id": job.get("agent_profile_id"),
        "idempotency_key": job["idempotency_key"],
        "status": current_status,
        "trace_id": job.get("trace_id") or run.get("trace_id"),
        "requested_skill_id": job.get("requested_skill_id"),
        "requested_tool_id": job.get("requested_tool_id"),
        "run_status": run.get("status"),
        "run_state": run.get("state"),
        "registry_version": run.get("registry_version"),
        "registry_fingerprint": run.get("registry_fingerprint"),
        "key_id": _external_agent_job_receipt_key_id(),
        "receipt_context_hash": context_hash,
        "evidence": evidence,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    existing_receipt = get_external_agent_job_receipt_for_context_hash(
        job_id=job["id"],
        client_id=job["client_id"],
        principal_id=job["principal_id"],
        status=current_status,
        receipt_context_hash=context_hash,
    )
    if existing_receipt:
        receipt_payload = existing_receipt.get("payload") or receipt_payload
        signature = existing_receipt.get("signature")
        stored = update_external_agent_job_receipt(
            job_id=job["id"],
            receipt_id=existing_receipt.get("id") or receipt_payload["receipt_id"],
            receipt_type=existing_receipt.get("receipt_type")
            or receipt_payload["receipt_type"],
            receipt_signature=signature,
            receipt_signature_algorithm=existing_receipt.get("signature_algorithm")
            or "hmac-sha256",
            receipt_payload=receipt_payload,
        )
        job.update(stored or {})
        return {
            **receipt_payload,
            "signature": signature,
            "signature_algorithm": existing_receipt.get("signature_algorithm")
            or "hmac-sha256",
        }
    signature = _sign_external_agent_job_receipt(receipt_payload)
    receipt_row = create_external_agent_job_receipt(
        receipt_id=receipt_payload["receipt_id"],
        job_id=job["id"],
        client_id=job["client_id"],
        principal_id=job["principal_id"],
        run_id=job["run_id"],
        receipt_type=receipt_payload["receipt_type"],
        status=current_status,
        receipt_context_hash=context_hash,
        signature=signature,
        signature_algorithm="hmac-sha256",
        payload=receipt_payload,
    )
    receipt_payload = receipt_row.get("payload") or receipt_payload
    signature = receipt_row.get("signature") or signature
    stored = update_external_agent_job_receipt(
        job_id=job["id"],
        receipt_id=receipt_row.get("id") or receipt_payload["receipt_id"],
        receipt_type=receipt_row.get("receipt_type") or receipt_payload["receipt_type"],
        receipt_signature=signature,
        receipt_signature_algorithm=receipt_row.get("signature_algorithm")
        or "hmac-sha256",
        receipt_payload=receipt_payload,
    )
    job.update(stored or {})
    return {
        **receipt_payload,
        "signature": signature,
        "signature_algorithm": "hmac-sha256",
    }


def _stored_external_agent_job_receipt(
    *, job: Dict[str, Any], run: Dict[str, Any]
) -> Dict[str, Any] | None:
    payload = job.get("receipt_payload") or {}
    signature = job.get("receipt_signature")
    if not payload or not signature:
        return None
    current_status = _job_status_from_run(run)
    stale_context = not _stored_receipt_context_matches_run(
        payload=payload, run=run, current_status=current_status
    )
    return {
        **payload,
        "signature": signature,
        "signature_algorithm": job.get("receipt_signature_algorithm"),
        "stale_context": stale_context,
        "refresh_required_for_latest_context": stale_context,
    }


def _stored_receipt_context_matches_run(
    *, payload: Dict[str, Any], run: Dict[str, Any], current_status: str
) -> bool:
    return bool(
        payload.get("status") == current_status
        and payload.get("run_status") == run.get("status")
        and payload.get("run_state") == run.get("state")
        and payload.get("registry_version") == run.get("registry_version")
        and payload.get("registry_fingerprint") == run.get("registry_fingerprint")
    )


def _external_agent_activity_items(
    *,
    job: Dict[str, Any],
    run: Dict[str, Any],
    receipts: List[Dict[str, Any]],
    events: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = [
        {
            "type": "job",
            "subtype": "external_agent_job_created",
            "status": job.get("status"),
            "timestamp": job.get("created_at"),
            "job_id": job.get("id"),
            "run_id": job.get("run_id"),
            "trace_id": job.get("trace_id") or run.get("trace_id"),
        }
    ]
    for receipt in receipts:
        payload = receipt.get("payload") or {}
        items.append(
            {
                "type": "receipt",
                "subtype": payload.get("receipt_type") or receipt.get("receipt_type"),
                "status": payload.get("status") or receipt.get("status"),
                "timestamp": payload.get("issued_at") or receipt.get("created_at"),
                "job_id": payload.get("job_id") or receipt.get("job_id"),
                "run_id": payload.get("run_id") or receipt.get("run_id"),
                "trace_id": payload.get("trace_id"),
                "receipt_id": payload.get("receipt_id") or receipt.get("id"),
                "signature_algorithm": receipt.get("signature_algorithm"),
            }
        )
    for event in events:
        items.append(
            {
                "type": "run_event",
                "subtype": event.get("event_type"),
                "status": event.get("status"),
                "timestamp": event.get("timestamp"),
                "job_id": job.get("id"),
                "run_id": event.get("run_id") or job.get("run_id"),
                "trace_id": event.get("trace_id") or job.get("trace_id"),
                "event_id": event.get("id"),
                "action_id": event.get("action_id"),
                "sequence": event.get("sequence"),
                "tool_id": event.get("tool_id"),
                "skill_id": event.get("skill_id"),
                "effect_class": event.get("effect_class"),
                "capability_name": event.get("capability_name"),
                "capability_version": event.get("capability_version"),
                "is_policy_event": event.get("is_policy_event"),
                "note": event.get("note"),
                "anchors": event.get("anchors") or {},
            }
        )
    return sorted(
        items,
        key=lambda item: str(item.get("timestamp") or ""),
    )


def _sign_external_agent_job_receipt(payload: Dict[str, Any]) -> str:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    signature = hmac.new(
        _external_agent_job_receipt_secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def _decode_external_agent_job_receipt_signature(
    signature: str,
) -> tuple[Dict[str, Any], bool]:
    try:
        payload_b64, provided_signature = signature.rsplit(".", 1)
    except ValueError:
        return {}, False
    expected_signature = hmac.new(
        _external_agent_job_receipt_secret().encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        return {}, False
    try:
        padding = "=" * (-len(payload_b64) % 4)
        payload_raw = base64.urlsafe_b64decode(payload_b64 + padding)
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        return {}, False
    return payload if isinstance(payload, dict) else {}, True


def _job_evidence_summary(*, deps: AppDeps, run: Dict[str, Any]) -> Dict[str, Any]:
    run_id = str(run.get("id") or "")
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=_ACTION_EVIDENCE_LIMIT + 1
    )
    events = deps.agent_events.list_agent_events(
        agent_run_id=run_id, limit=_EVENT_EVIDENCE_LIMIT + 1
    )
    actions_truncated = len(actions) > _ACTION_EVIDENCE_LIMIT
    events_truncated = len(events) > _EVENT_EVIDENCE_LIMIT
    actions = actions[:_ACTION_EVIDENCE_LIMIT]
    events = events[-_EVENT_EVIDENCE_LIMIT:]
    action_items = [
        {
            "id": action.get("id"),
            "sequence": action.get("sequence"),
            "status": action.get("status"),
            "capability_name": action.get("capability_name"),
            "capability_version": action.get("capability_version"),
            "tool_id": action.get("tool_id"),
            "skill_id": action.get("skill_id"),
            "effect_class": action.get("effect_class"),
            "inputs_hash": action.get("inputs_hash"),
            "outputs_hash": action.get("outputs_hash"),
            "registry_version": action.get("registry_version"),
            "registry_fingerprint": action.get("registry_fingerprint"),
            "tool_version": action.get("tool_version"),
            "skill_version": action.get("skill_version"),
            "receipt_id": action.get("receipt_id"),
            "error": action.get("error"),
        }
        for action in actions
    ]
    event_items = [
        {
            "id": event.get("id"),
            "sequence": event.get("sequence"),
            "event_type": event.get("event_type"),
            "status": event.get("status"),
            "action_id": event.get("action_id"),
            "capability_name": event.get("capability_name"),
            "capability_version": event.get("capability_version"),
            "tool_id": event.get("tool_id"),
            "skill_id": event.get("skill_id"),
            "effect_class": event.get("effect_class"),
            "is_policy_event": event.get("is_policy_event"),
            "timestamp": event.get("timestamp"),
            "anchors": event.get("anchors") or {},
        }
        for event in events
    ]
    latest_event = event_items[-1] if event_items else {}
    return {
        "action_count": len(action_items),
        "event_count": len(event_items),
        "complete": not actions_truncated and not events_truncated,
        "actions_complete": not actions_truncated,
        "events_complete": not events_truncated,
        "action_limit": _ACTION_EVIDENCE_LIMIT,
        "event_limit": _EVENT_EVIDENCE_LIMIT,
        "digest_scope": "complete" if not actions_truncated and not events_truncated else "bounded_window",
        "latest_event_id": latest_event.get("id"),
        "latest_event_timestamp": latest_event.get("timestamp"),
        "action_digest": _stable_digest(action_items),
        "event_digest": _stable_digest(event_items),
        "terminal_action_statuses": [
            {
                "id": action.get("id"),
                "sequence": action.get("sequence"),
                "status": action.get("status"),
                "inputs_hash": action.get("inputs_hash"),
                "outputs_hash": action.get("outputs_hash"),
                "error": action.get("error"),
            }
            for action in action_items
            if action.get("status") in {"executed", "failed", "rejected", "skipped"}
        ],
    }


def _receipt_context_hash(
    *,
    job: Dict[str, Any],
    run: Dict[str, Any],
    current_status: str,
    evidence: Dict[str, Any],
) -> str:
    return _stable_digest(
        {
            "job_id": job.get("id"),
            "run_id": job.get("run_id"),
            "client_id": job.get("client_id"),
            "principal_id": job.get("principal_id"),
            "status": current_status,
            "trace_id": job.get("trace_id") or run.get("trace_id"),
            "requested_skill_id": job.get("requested_skill_id"),
            "requested_tool_id": job.get("requested_tool_id"),
            "run_status": run.get("status"),
            "run_state": run.get("state"),
            "registry_version": run.get("registry_version"),
            "registry_fingerprint": run.get("registry_fingerprint"),
            "evidence": evidence,
        }
    )


def _stable_digest(payload: Any) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _set_external_agent_poll_headers(response: Response) -> None:
    response.headers["Retry-After"] = str(_POLL_RETRY_AFTER_SECONDS)
    response.headers["X-Agent-Poll-Interval-Seconds"] = str(_POLL_INTERVAL_SECONDS)
    response.headers["X-Agent-Receipt-Refresh"] = "explicit"


def _external_agent_job_receipt_key_id() -> str:
    settings = get_settings()
    if settings.registry_approval_signing_secret:
        return "registry-approval-signing-secret:v1"
    if settings.agent_principal_signing_secret:
        return "agent-principal-signing-secret:v1"
    return "local-development-external-agent-job-secret:v1"


def _external_agent_job_receipt_secret() -> str:
    settings = get_settings()
    secret = (
        settings.registry_approval_signing_secret
        or settings.agent_principal_signing_secret
    )
    if secret:
        return secret
    if settings.app_env != "prod":
        return "local-development-external-agent-job-secret"
    raise HTTPException(
        status_code=500,
        detail="AGENT_PRINCIPAL_SIGNING_SECRET is not configured",
    )


__all__ = ["router"]
