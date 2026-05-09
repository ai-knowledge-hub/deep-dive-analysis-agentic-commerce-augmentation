from __future__ import annotations

from typing import Any, Mapping

from fastapi import HTTPException, Request

from api.utils.principals import PrincipalContext, resolve_principal_context


def require_agent_run_create_principal_access(
    *,
    principal: PrincipalContext,
    requested_principal_type: str | None,
    requested_principal_id: str | None,
    requested_agent_profile_id: str | None,
) -> None:
    if principal.principal_type == "external_agent" and principal.auth_method != "bearer_token":
        raise HTTPException(
            status_code=401,
            detail="External-agent run creation requires a bearer token",
        )
    if principal.auth_method != "bearer_token":
        return
    if requested_principal_type and requested_principal_type != principal.principal_type:
        raise HTTPException(
            status_code=403,
            detail="principal_type does not match authenticated principal",
        )
    if requested_principal_id and requested_principal_id != principal.principal_id:
        raise HTTPException(
            status_code=403,
            detail="principal_id does not match authenticated principal",
        )
    if (
        requested_agent_profile_id
        and principal.agent_profile_id
        and requested_agent_profile_id != principal.agent_profile_id
    ):
        raise HTTPException(
            status_code=403,
            detail="agent_profile_id does not match authenticated principal",
        )
    scopes = set(principal.scopes or ())
    if "*" not in scopes and "agent_runs:write" not in scopes:
        raise HTTPException(
            status_code=403,
            detail="Missing required scope: agent_runs:write",
        )


def require_agent_run_control_access(
    *,
    request: Request,
    run: Mapping[str, Any],
    client_id: str,
    user_id: str | None,
    required_scope: str,
) -> PrincipalContext | None:
    """Protect external-agent-owned runs from tenant-only control calls."""

    principal_type = str(run.get("principal_type") or "human").strip()
    if principal_type != "external_agent":
        return None

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
            detail="External-agent run control requires a bearer token",
        )
    if principal.principal_type != "external_agent":
        raise HTTPException(
            status_code=403,
            detail="Authenticated principal is not an external agent",
        )
    if principal.principal_id != str(run.get("principal_id") or ""):
        raise HTTPException(
            status_code=403,
            detail="Authenticated principal does not own this agent run",
        )
    scopes = set(principal.scopes or ())
    if "*" not in scopes and required_scope not in scopes:
        raise HTTPException(
            status_code=403,
            detail=f"Missing required scope: {required_scope}",
        )
    return principal


__all__ = [
    "require_agent_run_control_access",
    "require_agent_run_create_principal_access",
]
