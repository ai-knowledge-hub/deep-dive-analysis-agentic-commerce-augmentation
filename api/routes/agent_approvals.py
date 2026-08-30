from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, StrictInt

from api.composition import default_deps
from api.utils.agent_run_authorization import require_agent_run_control_access
from api.utils.approval_authority import require_approval_authority
from api.utils.tenancy import require_client_id
from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_ledger import (
    ApprovalLedgerError,
    issue_action_approval_command,
    list_action_approvals,
)
from application.services.agent_runtime.commands.decisions import decide_agent_action


router = APIRouter(prefix="/agent-runs", tags=["agent-approvals"])


def _deps() -> AppDeps:
    return default_deps()


class AgentActionDecisionRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    decision: str = Field(..., min_length=1)
    idempotency_key: Optional[str] = None


class AgentApprovalCommandRequest(BaseModel):
    user_id: Optional[str] = None
    client_id: Optional[str] = None
    command_type: str = Field(..., min_length=1)
    idempotency_key: str = Field(..., min_length=1)
    approval_id: Optional[str] = None
    expected_sequence: Optional[StrictInt] = None
    ttl_seconds: Optional[StrictInt] = None
    revocation_reference: Optional[str] = None
    supersession_reference: Optional[str] = None


def _scoped_action_and_run(
    *, deps: AppDeps, action_id: str, client_id: str
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=client_id
    )
    if not action:
        raise HTTPException(status_code=404, detail="Agent action not found")
    run = deps.agent_runs.get_agent_run(
        run_id=str(action.get("agent_run_id") or ""), client_id=client_id
    )
    if not run:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return action, run


@router.post("/actions/{action_id}/decision")
def decide_action(
    action_id: str,
    payload: AgentActionDecisionRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    _, run = _scoped_action_and_run(
        deps=deps, action_id=action_id, client_id=client_id
    )
    authority = require_approval_authority(
        request=request,
        run=run,
        client_id=client_id,
        user_id=payload.user_id,
    )
    try:
        action = decide_agent_action(
            deps=deps,
            action_id=action_id,
            client_id=client_id,
            user_id=payload.user_id,
            decision=payload.decision,
            approving_authority=authority,
            idempotency_key=payload.idempotency_key
            or f"legacy-action-decision:{action_id}:{payload.decision.strip().lower()}",
        )
    except ApprovalLedgerError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "Agent action not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc
    return {"action": action}


@router.post("/actions/{action_id}/approval-commands")
def issue_action_approval(
    action_id: str,
    payload: AgentApprovalCommandRequest,
    request: Request,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    client_id = require_client_id(payload.client_id, payload.user_id)
    action, run = _scoped_action_and_run(
        deps=deps, action_id=action_id, client_id=client_id
    )
    authority = require_approval_authority(
        request=request,
        run=run,
        client_id=client_id,
        user_id=payload.user_id,
    )
    try:
        return issue_action_approval_command(
            deps=deps,
            run=run,
            action=action,
            command_type=payload.command_type,
            approving_authority=authority,
            idempotency_key=payload.idempotency_key,
            approval_id=payload.approval_id,
            expected_sequence=payload.expected_sequence,
            ttl_seconds=payload.ttl_seconds,
            revocation_reference=payload.revocation_reference,
            supersession_reference=payload.supersession_reference,
        )
    except ApprovalLedgerError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc


@router.get("/actions/{action_id}/approvals")
def get_action_approvals(
    action_id: str,
    request: Request,
    client_id: Optional[str] = None,
    user_id: Optional[str] = None,
    deps: AppDeps = Depends(_deps),
) -> Dict[str, Any]:
    scoped_client_id = require_client_id(client_id, user_id)
    _, run = _scoped_action_and_run(
        deps=deps, action_id=action_id, client_id=scoped_client_id
    )
    require_agent_run_control_access(
        request=request,
        run=run,
        client_id=scoped_client_id,
        user_id=user_id,
        required_scope="agent_runs:read",
    )
    return {
        "approvals": list_action_approvals(
            deps=deps,
            tenant_id=scoped_client_id,
            workflow_id=str(run["id"]),
            action_id=action_id,
        )
    }


__all__ = ["router"]
