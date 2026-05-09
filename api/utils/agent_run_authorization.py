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
    """Protect external-agent-owned runs from external-principal hijacking.

    Human user context is allowed to supervise runs scoped to its tenant. Bearer-token
    calls remain constrained to the external principal that owns the run.
    """

    run_principal_type = str(run.get("principal_type") or "human").strip()
    bearer_present = _request_has_bearer_token(request)
    if run_principal_type != "external_agent" and not bearer_present:
        return None

    principal = resolve_principal_context(
        request=request,
        client_id=client_id,
        user_id=user_id,
        principal_type=None,
        principal_id=None,
        agent_profile_id=None,
    )
    if principal.auth_method == "user_context" and principal.principal_type == "human":
        return principal
    if principal.auth_method != "bearer_token":
        raise HTTPException(
            status_code=401,
            detail="External-agent run supervision requires user context or owner bearer token",
        )
    if run_principal_type != "external_agent":
        if (
            principal.principal_type == run_principal_type
            and principal.principal_id == str(run.get("principal_id") or "")
        ):
            _require_scope(principal=principal, required_scope=required_scope)
            return principal
        _require_scope(principal=principal, required_scope="agent_runs:supervise")
        _require_scope(principal=principal, required_scope=required_scope)
        return principal
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
    _require_scope(principal=principal, required_scope=required_scope)
    return principal


def require_agent_run_list_access(
    *,
    request: Request,
    client_id: str,
    user_id: str | None,
    required_scope: str,
) -> PrincipalContext | None:
    if not _request_has_bearer_token(request):
        return None
    principal = resolve_principal_context(
        request=request,
        client_id=client_id,
        user_id=user_id,
        principal_type=None,
        principal_id=None,
        agent_profile_id=None,
    )
    _require_scope(principal=principal, required_scope=required_scope)
    return principal


def principal_has_scope(*, principal: PrincipalContext, scope: str) -> bool:
    scopes = set(principal.scopes or ())
    return "*" in scopes or scope in scopes


def filter_agent_runs_for_principal(
    *, runs: list[Mapping[str, Any]], principal: PrincipalContext | None
) -> list[Mapping[str, Any]]:
    if not principal or principal_has_scope(
        principal=principal, scope="agent_runs:supervise"
    ):
        return runs
    return [
        run
        for run in runs
        if str(run.get("principal_type") or "") == principal.principal_type
        and str(run.get("principal_id") or "") == principal.principal_id
    ]


def _request_has_bearer_token(request: Request) -> bool:
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    scheme, _, token = str(auth_header or "").partition(" ")
    return scheme.lower() == "bearer" and bool(token.strip())


def _require_scope(*, principal: PrincipalContext, required_scope: str) -> None:
    if principal_has_scope(principal=principal, scope=required_scope):
        return
    raise HTTPException(
        status_code=403,
        detail=f"Missing required scope: {required_scope}",
    )


__all__ = [
    "require_agent_run_control_access",
    "require_agent_run_create_principal_access",
    "require_agent_run_list_access",
    "principal_has_scope",
    "filter_agent_runs_for_principal",
]
