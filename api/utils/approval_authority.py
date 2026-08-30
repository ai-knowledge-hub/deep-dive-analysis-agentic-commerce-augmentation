from __future__ import annotations

from fastapi import HTTPException, Request

from api.utils.agent_run_authorization import require_agent_run_control_access
from api.utils.principals import PrincipalContext
from domain.workflow.approval import ApprovalAuthority, PrincipalType


def require_approval_authority(
    *,
    request: Request,
    run: dict,
    client_id: str,
    user_id: str | None,
) -> ApprovalAuthority:
    """Resolve an approval actor from the authenticated control context.

    Body fields may locate compatibility data, but approval authority must come
    from verified bearer claims. The current API has no authenticated human
    session contract, so user-context fallbacks fail closed.
    """

    principal = require_agent_run_control_access(
        request=request,
        run=run,
        client_id=client_id,
        user_id=user_id,
        required_scope="agent_runs:write",
    )
    if principal is None or principal.auth_method != "bearer_token":
        raise HTTPException(
            status_code=401,
            detail="Approval decisions require verified bearer authority",
        )
    return ApprovalAuthority(
        principal_type=_principal_type(principal),
        principal_id=principal.principal_id,
        authority_source=_authority_source(principal),
        authority_version=_authority_version(principal),
    )


def _principal_type(principal: PrincipalContext) -> PrincipalType:
    try:
        return PrincipalType(principal.principal_type)
    except ValueError as exc:
        raise HTTPException(
            status_code=403,
            detail="Authenticated principal type cannot make approval decisions",
        ) from exc


def _authority_source(principal: PrincipalContext) -> str:
    del principal
    return "agent-principal-token"


def _authority_version(principal: PrincipalContext) -> str:
    del principal
    return "agent-principal-signing-secret:v1"


__all__ = ["require_approval_authority"]
