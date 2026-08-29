from __future__ import annotations

from fastapi import HTTPException, Request

from api.utils.agent_run_authorization import require_agent_run_control_access
from api.utils.principals import PrincipalContext, resolve_principal_context
from api.utils.tenancy import require_client_role
from domain.workflow.approval import ApprovalAuthority, PrincipalType


def require_approval_authority(
    *,
    request: Request,
    run: dict,
    client_id: str,
    user_id: str | None,
) -> ApprovalAuthority:
    """Resolve an approval actor from the authenticated control context.

    Body fields may locate the compatibility tenant/user context, but they never
    directly populate the persisted authority object.
    """

    principal = require_agent_run_control_access(
        request=request,
        run=run,
        client_id=client_id,
        user_id=user_id,
        required_scope="agent_runs:write",
    )
    if principal is None:
        principal = resolve_principal_context(
            request=request,
            client_id=client_id,
            user_id=user_id,
            principal_type=None,
            principal_id=None,
            agent_profile_id=None,
        )
    if principal.auth_method == "tenant_context":
        raise HTTPException(
            status_code=401,
            detail="Approval decisions require authenticated user or bearer context",
        )
    if principal.auth_method == "user_context":
        require_client_role(
            client_id=client_id,
            user_id=principal.user_id,
            allowed_roles={"admin", "owner", "operator"},
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
    if principal.auth_method == "bearer_token":
        return "agent-principal-token"
    return "tenant-membership"


def _authority_version(principal: PrincipalContext) -> str:
    if principal.auth_method == "bearer_token":
        return "agent-principal-signing-secret:v1"
    return "tenant-membership:v1"


__all__ = ["require_approval_authority"]
