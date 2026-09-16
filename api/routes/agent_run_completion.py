"""Tenant-scoped completion authority and projection-repair API."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api.composition import default_deps
from api.runtime_composition import default_completion_coordinator
from api.utils.agent_run_authorization import (
    principal_has_scope,
    require_agent_run_control_access,
)
from api.utils.principals import PrincipalContext, resolve_principal_context
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.workflow_outcomes.contracts import OutcomeLedgerConflict
from application.services.workflow_outcomes.production import (
    SequentialCompletionCoordinator,
)
from infrastructure.db.workflow.outcome_rows import OutcomeLedgerDataError


router = APIRouter(prefix="/agent-runs", tags=["agent-runs"])
REPAIR_SCOPE = "completion_projections:repair"


class CompletionProjectionRepairRequest(BaseModel):
    client_id: Optional[str] = None
    user_id: Optional[str] = None
    idempotency_key: str = Field(..., min_length=1, max_length=200)


def _deps() -> AppDeps:
    return default_deps()


def _completion_coordinator(
    deps: AppDeps = Depends(_deps),
) -> SequentialCompletionCoordinator:
    return default_completion_coordinator(deps)


@router.get("/{run_id}/completion")
def get_agent_run_completion(
    run_id: str,
    request: Request,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    deps: AppDeps = Depends(_deps),
    coordinator: SequentialCompletionCoordinator = Depends(_completion_coordinator),
):
    scoped_client_id = require_client_id(client_id, user_id)
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=scoped_client_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=user_id,
        required_scope="agent_runs:read",
    )
    try:
        completion = coordinator.get_completion_read_model(
            tenant_id=scoped_client_id, workflow_id=run_id
        )
    except OutcomeLedgerDataError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "completion_projection_integrity_error",
                "message": str(exc),
            },
        ) from exc
    if completion is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {"completion": completion}


@router.post("/{run_id}/completion/repair")
def repair_agent_run_completion(
    run_id: str,
    payload: CompletionProjectionRepairRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
    coordinator: SequentialCompletionCoordinator = Depends(_completion_coordinator),
):
    scoped_client_id = require_client_id(payload.client_id, payload.user_id)
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=scoped_client_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    principal = _require_repair_operator(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=payload.user_id,
    )
    try:
        return coordinator.repair_completion_read_model(
            tenant_id=scoped_client_id,
            workflow_id=run_id,
            principal_id=principal.principal_id,
            idempotency_key=payload.idempotency_key,
        )
    except (OutcomeLedgerConflict, OutcomeLedgerDataError) as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "completion_projection_repair_conflict", "message": str(exc)},
        ) from exc


def _require_repair_operator(
    *,
    request: Request,
    run: dict,
    client_id: str,
    user_id: str | None,
) -> PrincipalContext:
    principal = resolve_principal_context(
        request=request,
        client_id=client_id,
        user_id=user_id,
        principal_type=None,
        principal_id=None,
        agent_profile_id=None,
    )
    if principal.auth_method != "bearer_token":
        raise HTTPException(
            status_code=401,
            detail="Completion projection repair requires verified bearer authority",
        )
    if principal.principal_type != "human":
        raise HTTPException(
            status_code=403, detail="Completion projection repair requires a human operator"
        )
    if not principal_has_scope(principal=principal, scope=REPAIR_SCOPE):
        raise HTTPException(status_code=403, detail=f"Missing required scope: {REPAIR_SCOPE}")
    if principal.principal_id != str(run.get("principal_id") or "") and not principal_has_scope(
        principal=principal, scope="agent_runs:supervise"
    ):
        raise HTTPException(
            status_code=403,
            detail="Operator does not own this run and lacks agent_runs:supervise",
        )
    return principal


__all__ = ["router"]
