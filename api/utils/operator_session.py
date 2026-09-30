"""Verify the narrow server-to-server operator browser session assertion."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from api.utils.principals import PrincipalContext, resolve_principal_context
from shared.config.env import get_settings


ASSERTION_HEADER = "x-operator-session-assertion"
ASSERTION_AUDIENCE = "operator-conversation-api"
ASSERTION_ISSUER = "operator-conversation-web-bff"
ASSERTION_SCHEMA_VERSION = 1
_ASSERTION_FIELDS = frozenset(
    {
        "schema_version",
        "aud",
        "iss",
        "sub",
        "client_id",
        "run_id",
        "iat",
        "exp",
        "jti",
    }
)


@dataclass(frozen=True)
class OperatorSessionIdentity:
    principal: PrincipalContext
    user_id: str


def resolve_operator_session_identity(
    *,
    request: Request,
    client_id: str | None,
    user_id: str | None,
    run_id: str,
) -> OperatorSessionIdentity:
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        principal = resolve_principal_context(
            request=request,
            client_id=client_id,
            user_id=user_id,
            principal_type=None,
            principal_id=None,
            agent_profile_id=None,
        )
        if principal.principal_type != "human":
            raise HTTPException(
                status_code=403,
                detail="Operator conversation requires an authenticated human principal",
            )
        authenticated_user_id = _human_user_id(principal.principal_id)
        _require_matching_selector("user_id", user_id, authenticated_user_id)
        return OperatorSessionIdentity(
            principal=principal, user_id=authenticated_user_id
        )

    assertion = request.headers.get(ASSERTION_HEADER)
    if not assertion:
        raise HTTPException(
            status_code=401,
            detail="Operator conversation requires an authenticated human session",
        )
    claims = _verify_operator_session_assertion(assertion)
    authenticated_user_id = str(claims["sub"])
    authenticated_client_id = str(claims["client_id"])
    if str(claims["run_id"]) != run_id:
        raise HTTPException(
            status_code=403,
            detail="run_id does not match authenticated operator session",
        )
    _require_matching_selector("client_id", client_id, authenticated_client_id)
    _require_matching_selector("user_id", user_id, authenticated_user_id)
    return OperatorSessionIdentity(
        principal=PrincipalContext(
            principal_type="human",
            principal_id=f"human:{authenticated_user_id}",
            client_id=authenticated_client_id,
            user_id=authenticated_user_id,
            agent_profile_id=None,
            auth_method="operator_bff_assertion",
            scopes=("agent_runs:read",),
        ),
        user_id=authenticated_user_id,
    )


def _verify_operator_session_assertion(assertion: str) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.operator_bff_signing_secret
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Operator browser session verification is not configured",
        )
    if len(assertion) > 4096:
        raise HTTPException(
            status_code=401, detail="Invalid operator session assertion"
        )
    try:
        payload_b64, provided_signature = assertion.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail="Malformed operator session assertion"
        ) from exc
    expected_signature = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(
            status_code=401, detail="Invalid operator session assertion"
        )
    try:
        payload = json.loads(_urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail="Invalid operator session assertion payload"
        ) from exc
    if not isinstance(payload, dict) or set(payload) != _ASSERTION_FIELDS:
        raise HTTPException(
            status_code=401, detail="Invalid operator session assertion contract"
        )
    if payload.get("schema_version") != ASSERTION_SCHEMA_VERSION:
        raise HTTPException(
            status_code=401, detail="Unsupported operator session assertion version"
        )
    if (
        payload.get("aud") != ASSERTION_AUDIENCE
        or payload.get("iss") != ASSERTION_ISSUER
    ):
        raise HTTPException(
            status_code=401, detail="Invalid operator session assertion scope"
        )
    for field in ("sub", "client_id", "run_id", "jti"):
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip() or len(value) > 256:
            raise HTTPException(
                status_code=401, detail="Invalid operator session assertion identity"
            )
    iat = payload.get("iat")
    exp = payload.get("exp")
    if type(iat) is not int or type(exp) is not int:
        raise HTTPException(
            status_code=401, detail="Invalid operator session assertion lifetime"
        )
    now = int(time.time())
    max_ttl = int(settings.operator_bff_assertion_max_ttl_seconds)
    if iat > now + 5 or exp <= now or exp <= iat or exp - iat > max_ttl:
        raise HTTPException(
            status_code=401, detail="Expired or invalid operator session assertion"
        )
    return payload


def _require_matching_selector(
    field: str, selector: str | None, authenticated_value: str
) -> None:
    if selector and selector != authenticated_value:
        raise HTTPException(
            status_code=403,
            detail=f"{field} does not match authenticated principal",
        )


def _human_user_id(principal_id: str) -> str:
    return str(principal_id).strip().removeprefix("human:")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


__all__ = [
    "ASSERTION_AUDIENCE",
    "ASSERTION_HEADER",
    "ASSERTION_ISSUER",
    "ASSERTION_SCHEMA_VERSION",
    "OperatorSessionIdentity",
    "resolve_operator_session_identity",
]
