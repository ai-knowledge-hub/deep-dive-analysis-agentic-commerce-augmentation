"""Verify the narrow browser assertion for one exact command confirmation."""

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
    command_type: str = "pause",
    action_id: str | None = None,
    retry_strategy: str | None = None,
    effect_execution_id: str | None = None,
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
    if command_type in {"approve", "reject", "retry", "reconcile_effect"}:
        if not action_id:
            raise HTTPException(
                status_code=400, detail="An exact action_id is required"
            )
        _match("action_id", action_id, str(claims.get("action_id") or ""))
    if command_type == "reconcile_effect":
        if not effect_execution_id:
            raise HTTPException(
                status_code=400, detail="An exact effect_execution_id is required"
            )
        _match(
            "effect_execution_id",
            effect_execution_id,
            str(claims.get("effect_execution_id") or ""),
        )
    if command_type == "retry":
        _match(
            "retry_strategy", retry_strategy, str(claims.get("retry_strategy") or "")
        )
        if retry_strategy != "same_action":
            raise HTTPException(
                status_code=400, detail="An exact retry strategy is required"
            )
    _match("command_type", command_type, str(claims["command_type"]))
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
            scopes=("operator_reconciliations:confirm",)
            if command_type == "reconcile_effect"
            else ("operator_retries:confirm",)
            if command_type == "retry"
            else ("operator_action_reviews:confirm",)
            if command_type in {"approve", "reject"}
            else ("operator_commands:confirm",),
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
    fields, version, audience, issuer = _assertion_contract(payload)
    if type(payload) is not dict or set(payload) != fields:
        raise HTTPException(
            status_code=401, detail="Invalid operator command assertion contract"
        )
    if (
        payload.get("schema_version") != version
        or payload.get("aud") != audience
        or payload.get("iss") != issuer
    ):
        raise HTTPException(status_code=401, detail="Invalid operator command scope")
    retry = payload["command_type"] == "retry"
    review = payload["command_type"] in {"approve", "reject"}
    reconcile = payload["command_type"] == "reconcile_effect"
    if retry and payload.get("retry_strategy") != "same_action":
        raise HTTPException(status_code=401, detail="Invalid retry strategy")
    for field in (
        "sub",
        "client_id",
        "run_id",
        "proposal_id",
        "jti",
        *(("action_id",) if review or retry or reconcile else ()),
        *(("effect_execution_id",) if reconcile else ()),
    ):
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


def _assertion_contract(payload):
    contracts = {
        "pause": (1, ASSERTION_AUDIENCE, ASSERTION_ISSUER, frozenset()),
        "resume": (1, ASSERTION_AUDIENCE, ASSERTION_ISSUER, frozenset()),
        "cancel": (1, ASSERTION_AUDIENCE, ASSERTION_ISSUER, frozenset()),
        "approve": (
            2,
            "operator-action-review-api",
            "operator-action-review-web-bff",
            {"action_id"},
        ),
        "reject": (
            2,
            "operator-action-review-api",
            "operator-action-review-web-bff",
            {"action_id"},
        ),
        "retry": (
            3,
            "operator-retry-api",
            "operator-retry-web-bff",
            {"action_id", "retry_strategy"},
        ),
        "reconcile_effect": (
            4,
            "operator-reconciliation-api",
            "operator-reconciliation-web-bff",
            {"action_id", "effect_execution_id"},
        ),
    }
    contract = (
        contracts.get(payload.get("command_type"))
        if isinstance(payload, dict)
        else None
    )
    if contract is None:
        raise HTTPException(status_code=401, detail="Invalid operator command scope")
    version, audience, issuer, extra = contract
    return _FIELDS | extra, version, audience, issuer
