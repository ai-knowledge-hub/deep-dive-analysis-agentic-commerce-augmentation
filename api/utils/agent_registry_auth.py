from __future__ import annotations

from fastapi import HTTPException, Request

from api.utils.principals import PrincipalContext, resolve_principal_context

_REGISTRY_WRITE_SCOPES = {"*", "registry:write", "agent_registry:write"}


def require_registry_write_access(request: Request) -> PrincipalContext:
    if not _request_has_bearer_token(request):
        raise HTTPException(
            status_code=401,
            detail="Registry mutation requires authenticated registry-write bearer token",
        )
    principal = resolve_principal_context(
        request=request,
        client_id=None,
        user_id=None,
        principal_type=None,
        principal_id=None,
        agent_profile_id=None,
    )
    if not set(principal.scopes or ()).intersection(_REGISTRY_WRITE_SCOPES):
        raise HTTPException(
            status_code=403,
            detail="Missing required registry write scope",
        )
    return principal


def _request_has_bearer_token(request: Request) -> bool:
    auth_header = request.headers.get("authorization") or request.headers.get("Authorization")
    scheme, _, token = str(auth_header or "").partition(" ")
    return scheme.lower() == "bearer" and bool(token.strip())


__all__ = ["require_registry_write_access"]
