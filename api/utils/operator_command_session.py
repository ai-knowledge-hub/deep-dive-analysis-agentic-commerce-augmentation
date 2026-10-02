"""Verify the narrow browser assertion for one pause-proposal confirmation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import HTTPException, Request

from api.utils.operator_session import OperatorSessionIdentity
from api.utils.principals import PrincipalContext, resolve_principal_context
from shared.config.env import get_settings


ASSERTION_HEADER = "x-operator-command-assertion"
ASSERTION_AUDIENCE = "operator-command-api"
ASSERTION_ISSUER = "operator-command-web-bff"
ASSERTION_SCHEMA_VERSION = 1
_FIELDS = frozenset(
    {
        "schema_version",
        "aud",
        "iss",
        "sub",
        "client_id",
        "run_id",
        "proposal_id",
        "proposal_digest",
        "command_type",
        "iat",
        "exp",
        "jti",
    }
)


def resolve_operator_command_identity(
    *,
    request: Request,
    client_id: str | None,
    user_id: str | None,
    run_id: str,
    proposal_id: str,
    proposal_digest: str,
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
                detail="Operator command confirmation requires a human principal",
            )
        authenticated_user_id = principal.principal_id.removeprefix("human:")
        _match("user_id", user_id, authenticated_user_id)
        return OperatorSessionIdentity(
            principal=principal, user_id=authenticated_user_id
        )

    assertion = request.headers.get(ASSERTION_HEADER)
    if not assertion:
        raise HTTPException(
            status_code=401,
            detail="Operator command confirmation requires an authenticated human session",
        )
    claims = _verify(assertion)
    _match("client_id", client_id, str(claims["client_id"]))
    _match("user_id", user_id, str(claims["sub"]))
    _match("run_id", run_id, str(claims["run_id"]))
    _match("proposal_id", proposal_id, str(claims["proposal_id"]))
    _match("proposal_digest", proposal_digest, str(claims["proposal_digest"]))
    return OperatorSessionIdentity(
        principal=PrincipalContext(
            principal_type="human",
            principal_id=f"human:{claims['sub']}",
            client_id=str(claims["client_id"]),
            user_id=str(claims["sub"]),
            agent_profile_id=None,
            auth_method="operator_command_bff_assertion",
            scopes=("operator_commands:confirm",),
        ),
        user_id=str(claims["sub"]),
    )


def _verify(assertion: str) -> dict[str, object]:
    settings = get_settings()
    secret = settings.operator_command_bff_signing_secret
    if not secret or len(secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Operator command browser verification is not configured",
        )
    if len(assertion) > 4096:
        raise HTTPException(
            status_code=401, detail="Invalid operator command assertion"
        )
    try:
        payload_b64, provided_signature = assertion.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail="Malformed operator command assertion"
        ) from exc
    expected = hmac.new(
        secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected):
        raise HTTPException(
            status_code=401, detail="Invalid operator command assertion"
        )
    try:
        payload = json.loads(_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail="Invalid operator command assertion payload"
        ) from exc
    if type(payload) is not dict or set(payload) != _FIELDS:
        raise HTTPException(
            status_code=401, detail="Invalid operator command assertion contract"
        )
    if (
        payload.get("schema_version") != ASSERTION_SCHEMA_VERSION
        or payload.get("aud") != ASSERTION_AUDIENCE
        or payload.get("iss") != ASSERTION_ISSUER
        or payload.get("command_type") != "pause"
    ):
        raise HTTPException(status_code=401, detail="Invalid operator command scope")
    for field in ("sub", "client_id", "run_id", "proposal_id", "jti"):
        value = payload.get(field)
        if (
            type(value) is not str
            or not value
            or value != value.strip()
            or len(value) > 256
        ):
            raise HTTPException(
                status_code=401, detail="Invalid operator command identity"
            )
    digest = payload.get("proposal_digest")
    if (
        type(digest) is not str
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise HTTPException(status_code=401, detail="Invalid operator command digest")
    iat = payload.get("iat")
    exp = payload.get("exp")
    if type(iat) is not int or type(exp) is not int:
        raise HTTPException(status_code=401, detail="Invalid operator command lifetime")
    now = int(time.time())
    max_ttl = int(settings.operator_command_bff_assertion_max_ttl_seconds)
    if iat > now + 5 or exp <= now or exp <= iat or exp - iat > max_ttl:
        raise HTTPException(
            status_code=401, detail="Expired or invalid operator command assertion"
        )
    return payload


def _match(field: str, supplied: str | None, authenticated: str) -> None:
    if supplied is not None and supplied != authenticated:
        raise HTTPException(
            status_code=403,
            detail=f"{field} does not match authenticated command scope",
        )


def _decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("ascii"))


__all__ = [
    "ASSERTION_AUDIENCE",
    "ASSERTION_HEADER",
    "ASSERTION_ISSUER",
    "ASSERTION_SCHEMA_VERSION",
    "resolve_operator_command_identity",
]
