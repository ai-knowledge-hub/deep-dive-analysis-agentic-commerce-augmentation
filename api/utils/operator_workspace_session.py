"""Authenticate pre-run conversation operations and exact creation confirmation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException, Request
from api.utils.principals import PrincipalContext, resolve_principal_context
from shared.config.env import get_settings

HEADER = "x-operator-workspace-assertion"


def resolve_workspace_identity(
    *,
    request: Request,
    client_id: str | None,
    session_id: str,
    operation: str,
    proposal_id: str = "",
    proposal_digest: str = "",
) -> PrincipalContext:
    if (request.headers.get("authorization") or "").lower().startswith("bearer "):
        principal = resolve_principal_context(
            request=request,
            client_id=client_id,
            user_id=None,
            principal_type=None,
            principal_id=None,
            agent_profile_id=None,
        )
        if principal.principal_type != "human":
            raise HTTPException(403, "An authenticated human is required")
        return principal
    settings = get_settings()
    secret = (
        settings.operator_command_bff_signing_secret
        if operation == "confirm"
        else settings.operator_bff_signing_secret
    )
    if operation == "confirm" and secret == settings.operator_bff_signing_secret:
        raise HTTPException(
            503, "Creation requires a separate confirmation signing secret"
        )
    if not secret or len(secret) < 32:
        raise HTTPException(503, "Workspace authentication is unavailable")
    assertion = request.headers.get(HEADER) or ""
    try:
        if len(assertion) > 4096:
            raise ValueError("oversized assertion")
        encoded, signature = assertion.rsplit(".", 1)
        expected = hmac.new(
            secret.encode(), encoded.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError("signature")
        claims = json.loads(
            base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        )
        fields = {
            "schema_version",
            "aud",
            "iss",
            "sub",
            "client_id",
            "session_id",
            "operation",
            "proposal_id",
            "proposal_digest",
            "iat",
            "exp",
            "jti",
        }
        audience = (
            "operator-run-creation-api"
            if operation == "confirm"
            else "operator-workspace-api"
        )
        if (
            set(claims) != fields
            or claims["schema_version"] != 1
            or claims["aud"] != audience
            or claims["iss"] != "operator-workspace-web-bff"
        ):
            raise ValueError("contract")
        for field in ("sub", "client_id", "session_id", "jti"):
            if (
                not isinstance(claims[field], str)
                or not claims[field].strip()
                or len(claims[field]) > 256
            ):
                raise ValueError("identity")
        now = int(time.time())
        iat, exp = claims["iat"], claims["exp"]
        if (
            type(iat) is not int
            or type(exp) is not int
            or iat > now + 5
            or exp <= now
            or exp <= iat
            or exp - iat > 60
        ):
            raise ValueError("lifetime")
    except Exception as exc:
        raise HTTPException(401, "Invalid workspace assertion") from exc
    if (
        claims["session_id"],
        claims["operation"],
        claims["proposal_id"],
        claims["proposal_digest"],
    ) != (session_id, operation, proposal_id, proposal_digest):
        raise HTTPException(
            403, "Assertion does not match the exact workspace operation"
        )
    if client_id and claims["client_id"] != client_id:
        raise HTTPException(403, "Tenant does not match authenticated identity")
    return PrincipalContext(
        principal_type="human",
        principal_id=f"human:{claims['sub']}",
        client_id=claims["client_id"],
        user_id=claims["sub"],
        agent_profile_id=None,
        auth_method="operator_workspace_bff_assertion",
        scopes=("agent_runs:read", "agent_runs:write")
        if operation == "confirm"
        else ("agent_runs:read",),
    )
