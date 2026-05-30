from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, Security
from fastapi.security import HTTPBearer

from api.composition import default_deps
from api.routes.external_agent_job_models import (
    ExternalAgentJobActivityResponse,
    ExternalAgentJobCreateRequest,
    ExternalAgentJobEventListResponse,
    ExternalAgentJobReceiptListResponse,
    ExternalAgentJobReceiptResponse,
    ExternalAgentJobReceiptVerificationResponse,
    ExternalAgentJobReceiptVerifyRequest,
    ExternalAgentJobResponse,
)
from api.utils.agent_profile_defaults import agent_profile_defaults
from api.utils.agent_registry_runtime import registry_payload_and_fingerprint
from api.utils.external_agent_errors import external_agent_error
from api.utils.principals import PrincipalContext, resolve_principal_context
from application.ports.deps import AppDeps
from application.services.agent_runtime.events import list_agent_run_events_page
from api.utils.external_agent_jobs import (
    POLL_RETRY_AFTER_SECONDS,
    ensure_external_agent_job_receipt,
    external_agent_activity_items,
    job_status_from_run,
    job_status_payload,
    list_receipt_payloads,
    set_external_agent_poll_headers,
    stored_external_agent_job_receipt,
    sync_job_status_from_run,
    verify_external_agent_job_receipt,
)
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    list_skill_specs,
    select_skill_for_tool_id,
)
from application.services.agent_runtime.registry import (
    get_tool_spec,
    non_executable_tool_contract,
)
from application.services.agent_runtime.runs import (
    AgentRunPlanError,
    create_agent_run_with_initial_plan,
)
from infrastructure.db.agent.agent_registry import ensure_agent_registry_version
from infrastructure.db.agent.external_agent_jobs import (
    create_external_agent_job,
    delete_external_agent_job_idempotency_reservation,
    get_external_agent_job,
    get_external_agent_job_by_idempotency_key,
    get_external_agent_job_idempotency_reservation,
    list_external_agent_job_receipts,
    reserve_external_agent_job_idempotency,
    update_external_agent_job_status,
)

_AGENT_BEARER = HTTPBearer(auto_error=False)

router = APIRouter(
    prefix="/external-agent/jobs",
    tags=["external-agent-jobs"],
    dependencies=[Security(_AGENT_BEARER)],
)

_TERMINAL_JOB_STATUSES = {"completed", "failed", "canceled"}


def _deps() -> AppDeps:
    return default_deps()


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
            raise external_agent_error(
                status_code=409,
                code="idempotency_payload_mismatch",
                message="idempotency_key already used with a different request payload",
            )
        run = deps.agent_runs.get_agent_run(
            run_id=existing["run_id"], client_id=principal.client_id
        )
        if not run:
            raise _idempotent_job_run_missing(job_id=str(existing.get("id") or ""))
        job = job_status_payload(job=existing, run=run)
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
                raise external_agent_error(
                    status_code=409,
                    code="idempotency_payload_mismatch",
                    message="idempotency_key already used with a different request payload",
                )
            run = deps.agent_runs.get_agent_run(
                run_id=existing["run_id"], client_id=principal.client_id
            )
            if not run:
                raise _idempotent_job_run_missing(job_id=str(existing.get("id") or ""))
            job = job_status_payload(job=existing, run=run)
            return ExternalAgentJobResponse(job=job, run=run, idempotent_replay=True)
        reservation = get_external_agent_job_idempotency_reservation(
            client_id=principal.client_id,
            principal_id=principal.principal_id,
            idempotency_key=payload.idempotency_key,
        )
        if reservation and reservation.get("request_hash") != request_hash:
            raise external_agent_error(
                status_code=409,
                code="idempotency_payload_mismatch",
                message="idempotency_key already reserved with a different request payload",
            )
        raise external_agent_error(
            status_code=409,
            code="idempotency_in_progress",
            message="idempotent job creation is already in progress; retry with the same idempotency_key",
            retryable=True,
            retry_after_seconds=POLL_RETRY_AFTER_SECONDS,
        )

    registry_payload, active_registry_fingerprint = registry_payload_and_fingerprint(
        client_id=principal.client_id
    )
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
            objective=_job_objective(payload=payload, resolved=resolved),
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
            agent_profile_defaults=agent_profile_defaults(
                agent_profile_id=principal.agent_profile_id,
                client_id=principal.client_id,
            ),
            preferred_skill_id=resolved["skill_id"],
        )
    except AgentRunPlanError as exc:
        delete_external_agent_job_idempotency_reservation(
            client_id=principal.client_id,
            principal_id=principal.principal_id,
            idempotency_key=payload.idempotency_key,
        )
        raise external_agent_error(
            status_code=400,
            code="invalid_job_plan",
            message=str(exc),
            retryable=False,
        ) from exc
    response = {
        "job_id": None,
        "run_id": run["id"],
        "status": job_status_from_run(run),
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
        raise external_agent_error(
            status_code=409,
            code="idempotency_payload_mismatch",
            message="idempotency_key already used with a different request payload",
        )
    if created["run_id"] != run["id"]:
        deps.agent_runs.delete_agent_run(run_id=run["id"], client_id=principal.client_id)
        existing_run = deps.agent_runs.get_agent_run(
            run_id=created["run_id"], client_id=principal.client_id
        )
        if not existing_run:
            raise _idempotent_job_run_missing(job_id=str(created.get("id") or ""))
        job = job_status_payload(job=created, run=existing_run)
        return ExternalAgentJobResponse(job=job, run=existing_run, idempotent_replay=True)
    response["job_id"] = created["id"]
    created = update_external_agent_job_status(
        job_id=created["id"], status=response["status"], response=response
    ) or created
    return ExternalAgentJobResponse(job=job_status_payload(job=created, run=run), run=run)


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
        raise _external_agent_job_not_found(job_id=job_id)
    run = deps.agent_runs.get_agent_run(run_id=job["run_id"], client_id=principal.client_id)
    if not run:
        raise _external_agent_job_run_not_found(job_id=job_id)
    job = sync_job_status_from_run(job=job, run=run)
    set_external_agent_poll_headers(response)
    return ExternalAgentJobResponse(job=job_status_payload(job=job, run=run), run=run)


@router.get("/{job_id}/receipt", response_model_exclude_none=True)
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
    current_status = job_status_from_run(run)
    if refresh or current_status in _TERMINAL_JOB_STATUSES:
        receipt = ensure_external_agent_job_receipt(deps=deps, job=job, run=run)
    else:
        receipt = stored_external_agent_job_receipt(job=job, run=run)
        if not receipt:
            raise external_agent_error(
                status_code=404,
                code="external_agent_receipt_not_available",
                message=(
                    "No stored receipt exists for this job status; call with "
                    "refresh=true to mint one or poll until the job reaches a "
                    "terminal status."
                ),
                retryable=True,
                retry_after_seconds=POLL_RETRY_AFTER_SECONDS,
                context={
                    "job_id": job_id,
                    "status": current_status,
                    "refresh_available": True,
                    "refresh_query": "refresh=true",
                },
            )
    set_external_agent_poll_headers(response)
    return ExternalAgentJobReceiptResponse(receipt=receipt)


@router.post("/{job_id}/receipt/verify")
def verify_external_agent_job_receipt_route(
    job_id: str,
    payload: ExternalAgentJobReceiptVerifyRequest,
    request: Request,
    response: Response,
    deps: AppDeps = Depends(_deps),
) -> ExternalAgentJobReceiptVerificationResponse:
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
    set_external_agent_poll_headers(response)
    return verify_external_agent_job_receipt(
        receipt=payload.receipt,
        job=job,
        client_id=principal.client_id,
    )


@router.get("/{job_id}/receipts", response_model_exclude_none=True)
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
    receipts = list_receipt_payloads(rows)
    set_external_agent_poll_headers(response)
    return ExternalAgentJobReceiptListResponse(receipts=receipts)


@router.get("/{job_id}/activity", response_model_exclude_none=True)
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
        raise _external_agent_event_page_not_found(
            job_id=job_id,
            reason=str(exc),
            before=before,
            after=after,
            event_id=event_id,
        ) from exc
    items = external_agent_activity_items(
        job=job,
        run=run,
        receipts=receipt_rows,
        events=page["events"],
    )
    set_external_agent_poll_headers(response)
    return ExternalAgentJobActivityResponse(
        job=job_status_payload(job=job, run=run),
        summary={
            "status": job_status_from_run(run),
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
        raise _external_agent_event_page_not_found(
            job_id=job_id,
            reason=str(exc),
            before=before,
            after=after,
            event_id=event_id,
        ) from exc
    payload = page.to_dict()
    sync_job_status_from_run(job=job, run=run)
    set_external_agent_poll_headers(response)
    return ExternalAgentJobEventListResponse(
        events=payload["events"], page=payload["page"]
    )


def _require_external_agent_principal(*, request: Request) -> PrincipalContext:
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    scheme, _, token = str(auth_header or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise external_agent_error(
            status_code=401,
            code="external_agent_auth_required",
            message="External agent jobs require an external_agent bearer token",
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
        raise external_agent_error(
            status_code=401,
            code="external_agent_auth_required",
            message="External agent jobs require an external_agent bearer token",
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
        raise _external_agent_job_not_found(job_id=job_id)
    run = deps.agent_runs.get_agent_run(run_id=job["run_id"], client_id=principal.client_id)
    if not run:
        raise _external_agent_job_run_not_found(job_id=job_id)
    job = sync_job_status_from_run(job=job, run=run)
    return job, run


def _external_agent_job_not_found(*, job_id: str) -> HTTPException:
    return external_agent_error(
        status_code=404,
        code="external_agent_job_not_found",
        message="External agent job not found",
        context={"job_id": job_id},
    )


def _external_agent_job_run_not_found(*, job_id: str) -> HTTPException:
    return external_agent_error(
        status_code=404,
        code="external_agent_job_run_not_found",
        message="External agent job run not found",
        context={"job_id": job_id},
    )


def _external_agent_event_page_not_found(
    *,
    job_id: str,
    reason: str,
    before: Optional[str] = None,
    after: Optional[str] = None,
    event_id: Optional[str] = None,
) -> HTTPException:
    context = {"job_id": job_id}
    if before:
        context["before"] = before
    if after:
        context["after"] = after
    if event_id:
        context["event_id"] = event_id
    return external_agent_error(
        status_code=404,
        code="external_agent_event_page_not_found",
        message="External agent event page not found",
        context={**context, "reason": reason},
    )


def _idempotent_job_run_missing(*, job_id: str) -> HTTPException:
    return external_agent_error(
        status_code=409,
        code="idempotent_job_run_missing",
        message="idempotent job run is missing",
        context={"job_id": job_id},
    )


def _resolve_requested_runtime_contract(
    payload: ExternalAgentJobCreateRequest,
) -> Dict[str, Any]:
    capability_name = str(payload.capability_name or "").strip() or None
    tool_id = str(payload.tool_id or "").strip() or None
    if capability_name and not tool_id:
        tool_id = capability_to_tool_id(capability_name)
    tool = get_tool_spec(tool_id) if tool_id else None
    if tool_id and not tool:
        if _is_declared_non_executable_tool(tool_id):
            contract_context = non_executable_tool_contract(tool_id)
            raise external_agent_error(
                status_code=400,
                code="declared_non_executable_tool",
                message=(
                    f"Tool '{tool_id}' is declared in the registry as a "
                    "non-executable readiness boundary and cannot create jobs"
                ),
                context={
                    "tool_id": tool_id,
                    "executable": False,
                    **contract_context,
                },
            )
        raise external_agent_error(
            status_code=400,
            code="unsupported_tool",
            message=f"Unsupported tool_id: {tool_id}",
        )
    if tool and not capability_name:
        capability_name = tool.capability_name

    skill_id = str(payload.skill_id or "").strip() or None
    if skill_id and skill_id not in {skill.id for skill in list_skill_specs()}:
        raise external_agent_error(
            status_code=400,
            code="unsupported_skill",
            message=f"Unsupported skill_id: {skill_id}",
        )
    if tool_id:
        selected = select_skill_for_tool_id(tool_id, preferred_skill_id=skill_id)
        if skill_id and (not selected or selected.id != skill_id):
            raise external_agent_error(
                status_code=400,
                code="incompatible_skill_tool",
                message=f"Skill '{skill_id}' cannot use tool '{tool_id}'",
            )
        skill_id = selected.id if selected else skill_id

    allowed_capabilities = [
        str(item).strip() for item in payload.allowed_capabilities if str(item).strip()
    ]
    if capability_name and capability_name not in allowed_capabilities:
        allowed_capabilities = [capability_name, *allowed_capabilities]
    if not allowed_capabilities:
        raise external_agent_error(
            status_code=400,
            code="missing_runtime_target",
            message="External agent job requires a tool_id, capability_name, or allowed_capabilities",
        )
    plan_mode = str(
        payload.plan_mode or ("single_tool" if capability_name else "workflow")
    ).strip().lower()
    if plan_mode not in {"single_tool", "workflow"}:
        raise external_agent_error(
            status_code=400,
            code="invalid_plan_mode",
            message="plan_mode must be 'single_tool' or 'workflow'",
        )
    if plan_mode == "single_tool":
        if not capability_name:
            raise external_agent_error(
                status_code=400,
                code="single_tool_target_required",
                message="single_tool plan_mode requires a tool_id or capability_name",
            )
        allowed_capabilities = [capability_name]
    return {
        "skill_id": skill_id,
        "tool_id": tool_id,
        "allowed_capabilities": allowed_capabilities,
        "plan_mode": plan_mode,
        "scope_tool_ids": _tool_ids_for_capabilities(allowed_capabilities),
        "scope_skill_ids": _dedupe_ids(
            [
                *_scope_skill_ids_for_capabilities(
                    allowed_capabilities=allowed_capabilities,
                    requested_capability_name=capability_name,
                    requested_skill_id=skill_id,
                ),
                *([skill_id] if skill_id else []),
            ]
        ),
    }


def _job_objective(
    *, payload: ExternalAgentJobCreateRequest, resolved: Dict[str, Any]
) -> Dict[str, Any]:
    objective = dict(payload.objective or {})
    if payload.brand_id:
        objective["brand_id"] = payload.brand_id
    if payload.product_id:
        objective["product_id"] = payload.product_id
    return {
        **objective,
        "external_job": True,
        "requested_skill_id": resolved["skill_id"],
        "requested_tool_id": resolved["tool_id"],
        "plan_mode": resolved["plan_mode"],
    }


def _require_requested_skill_tool_scopes(
    principal: PrincipalContext, *, skill_ids: List[str], tool_ids: List[str]
) -> None:
    for tool_id in tool_ids:
        if not _has_any_scope(principal, f"tool:{tool_id}", "tools:*"):
            raise external_agent_error(
                status_code=403,
                code="missing_tool_scope",
                message=f"Missing scope for tool '{tool_id}'",
                context={"required": [f"tool:{tool_id}", "tools:*"]},
            )
    for skill_id in skill_ids:
        if not _has_any_scope(principal, f"skill:{skill_id}", "skills:*"):
            raise external_agent_error(
                status_code=403,
                code="missing_skill_scope",
                message=f"Missing scope for skill '{skill_id}'",
                context={"required": [f"skill:{skill_id}", "skills:*"]},
            )


def _is_declared_non_executable_tool(tool_id: str) -> bool:
    requested_tool_id = str(tool_id or "").strip()
    if not requested_tool_id or get_tool_spec(requested_tool_id):
        return False
    return any(
        requested_tool_id in skill.tool_ids
        for skill in list_skill_specs()
    )


def _tool_ids_for_capabilities(capability_names: List[str]) -> List[str]:
    tool_ids: List[str] = []
    for capability_name in capability_names:
        tool_id = capability_to_tool_id(capability_name)
        if not tool_id or not get_tool_spec(tool_id):
            raise external_agent_error(
                status_code=400,
                code="unsupported_capability",
                message=f"Unsupported capability_name: {capability_name}",
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
        raise external_agent_error(
            status_code=403,
            code="missing_external_agent_scope",
            message="Missing required external agent scope",
            context={"required": list(required)},
        )


def _has_any_scope(principal: PrincipalContext, *required: str) -> bool:
    scopes = set(principal.scopes or ())
    return "*" in scopes or any(scope in scopes for scope in required)


def _request_hash(payload: Dict[str, Any]) -> str:
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()



__all__ = ["router"]
