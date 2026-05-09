from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, Request

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import to_json
from shared.config.env import get_settings

from api.utils.tenancy import require_client_id


@dataclass(frozen=True)
class PrincipalContext:
    principal_type: str
    principal_id: str
    client_id: str
    user_id: str | None
    agent_profile_id: str | None
    auth_method: str
    scopes: tuple[str, ...] = ()


def build_agent_principal_token(
    *,
    principal_id: str,
    client_id: str,
    principal_type: str = "external_agent",
    agent_profile_id: str | None = None,
    scopes: list[str] | tuple[str, ...] | None = None,
    exp: int | None = None,
    signing_secret: str | None = None,
) -> str:
    settings = get_settings()
    secret = signing_secret or settings.agent_principal_signing_secret
    if not secret:
        raise ValueError("AGENT_PRINCIPAL_SIGNING_SECRET is not configured")
    now = int(time.time())
    ttl_seconds = max(
        1,
        min(
            int(settings.agent_principal_token_ttl_seconds),
            int(settings.agent_principal_token_max_ttl_seconds),
        ),
    )
    payload = {
        "principal_id": principal_id,
        "client_id": client_id,
        "principal_type": principal_type,
        "iat": now,
        "exp": int(exp) if exp is not None else now + ttl_seconds,
        "jti": str(uuid.uuid4()),
        "kid": _agent_principal_token_key_id(),
        "aud": settings.agent_principal_token_audience,
        "iss": settings.agent_principal_token_issuer,
    }
    if agent_profile_id:
        payload["agent_profile_id"] = agent_profile_id
    if scopes:
        payload["scopes"] = list(scopes)
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_b64 = _urlsafe_b64encode(payload_json)
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def agent_principal_token_metadata() -> dict[str, Any]:
    settings = get_settings()
    return {
        "token_type": "bearer",
        "signing_algorithm": "hmac-sha256",
        "current_key_id": _agent_principal_token_key_id(),
        "audience": settings.agent_principal_token_audience,
        "issuer": settings.agent_principal_token_issuer,
        "default_ttl_seconds": int(settings.agent_principal_token_ttl_seconds),
        "max_ttl_seconds": int(settings.agent_principal_token_max_ttl_seconds),
        "rotation_supported": False,
        "issuer_managed": True,
    }


def resolve_principal_context(
    *,
    request: Request,
    client_id: str | None,
    user_id: str | None,
    principal_type: str | None,
    principal_id: str | None,
    agent_profile_id: str | None,
) -> PrincipalContext:
    bearer = _bearer_token(request)
    if bearer:
        claims = _verify_agent_principal_token(bearer)
        token_client_id = str(claims.get("client_id") or "").strip()
        if not token_client_id:
            raise HTTPException(
                status_code=401, detail="Agent principal token missing client_id"
            )
        if client_id and client_id != token_client_id:
            raise HTTPException(
                status_code=403,
                detail="client_id does not match authenticated principal scope",
            )
        resolved = PrincipalContext(
            principal_type=str(
                claims.get("principal_type") or principal_type or "external_agent"
            ).strip(),
            principal_id=str(claims.get("principal_id") or "").strip(),
            client_id=token_client_id,
            user_id=user_id,
            agent_profile_id=str(claims.get("agent_profile_id") or "").strip() or None,
            auth_method="bearer_token",
            scopes=tuple(
                str(item).strip()
                for item in list(claims.get("scopes") or [])
                if str(item).strip()
            ),
        )
        if not resolved.principal_id:
            raise HTTPException(
                status_code=401, detail="Agent principal token missing principal_id"
            )
        _assert_principal_is_active(
            principal_id=resolved.principal_id,
            principal_type=resolved.principal_type,
            tenant_id=resolved.client_id,
        )
        ensure_principal(
            principal_id=resolved.principal_id,
            principal_type=resolved.principal_type,
            tenant_id=resolved.client_id,
            display_name=resolved.principal_id,
            metadata={
                "auth_method": resolved.auth_method,
                "scopes": list(resolved.scopes),
                "agent_profile_id": resolved.agent_profile_id,
            },
        )
        return resolved

    resolved_client_id = require_client_id(client_id, user_id)
    resolved_principal_type = str(principal_type or "human").strip().lower()
    resolved_principal_id = (
        str(principal_id).strip()
        if principal_id is not None and str(principal_id).strip()
        else _default_human_principal_id(
            user_id=user_id,
            client_id=resolved_client_id,
            principal_type=resolved_principal_type,
        )
    )
    resolved = PrincipalContext(
        principal_type=resolved_principal_type,
        principal_id=resolved_principal_id,
        client_id=resolved_client_id,
        user_id=user_id,
        agent_profile_id=agent_profile_id,
        auth_method="user_context" if user_id else "tenant_context",
    )
    ensure_principal(
        principal_id=resolved.principal_id,
        principal_type=resolved.principal_type,
        tenant_id=resolved.client_id,
        display_name=user_id or resolved.principal_id,
        metadata={
            "auth_method": resolved.auth_method,
            "user_id": user_id,
            "agent_profile_id": agent_profile_id,
        },
    )
    return resolved


def ensure_principal(
    *,
    principal_id: str,
    principal_type: str,
    tenant_id: str | None,
    display_name: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO principals (
            id,
            principal_type,
            tenant_id,
            display_name,
            metadata_json
        )
        VALUES (?, ?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            principal_type = excluded.principal_type,
            tenant_id = COALESCE(excluded.tenant_id, principals.tenant_id),
            display_name = COALESCE(excluded.display_name, principals.display_name),
            metadata_json = COALESCE(excluded.metadata_json, principals.metadata_json),
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            principal_id,
            principal_type,
            tenant_id,
            display_name,
            to_json(metadata) or to_json({}),
        ),
    )
    conn.commit()


def _assert_principal_is_active(
    *, principal_id: str, principal_type: str, tenant_id: str
) -> None:
    row = (
        get_connection()
        .execute(
            """
            SELECT status, principal_type, tenant_id
            FROM principals
            WHERE id = ?
            """,
            (principal_id,),
        )
        .fetchone()
    )
    if not row:
        return
    if str(row["principal_type"] or "") != principal_type:
        raise HTTPException(
            status_code=403,
            detail="Authenticated principal type does not match registry record",
        )
    row_tenant = str(row["tenant_id"] or "")
    if row_tenant and row_tenant != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Authenticated principal tenant does not match registry record",
        )
    if str(row["status"] or "").strip().lower() != "active":
        raise HTTPException(status_code=401, detail="Agent principal is not active")


def _default_human_principal_id(
    *, user_id: str | None, client_id: str, principal_type: str
) -> str:
    if principal_type != "human":
        return f"{principal_type}:{client_id}:default"
    if user_id:
        return f"human:{user_id}"
    return f"human:{client_id}:operator"


def _bearer_token(request: Request) -> str | None:
    auth_header = request.headers.get("authorization") or request.headers.get(
        "Authorization"
    )
    if not auth_header:
        return None
    scheme, _, token = auth_header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _verify_agent_principal_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    secret = settings.agent_principal_signing_secret
    if not secret:
        raise HTTPException(
            status_code=401, detail="Agent principal signing secret is not configured"
        )
    try:
        payload_b64, provided_signature = token.rsplit(".", 1)
    except ValueError as exc:
        raise HTTPException(
            status_code=401, detail="Malformed agent principal token"
        ) from exc
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        raise HTTPException(status_code=401, detail="Invalid agent principal token")
    try:
        payload = json.loads(_urlsafe_b64decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(
            status_code=401, detail="Invalid agent principal token payload"
        ) from exc
    exp = payload.get("exp")
    if exp is None:
        raise HTTPException(status_code=401, detail="Agent principal token missing exp")
    now = int(time.time())
    if int(exp) < now:
        raise HTTPException(status_code=401, detail="Expired agent principal token")
    iat = payload.get("iat")
    if iat is None:
        raise HTTPException(status_code=401, detail="Agent principal token missing iat")
    if int(iat) > now + 60:
        raise HTTPException(
            status_code=401, detail="Agent principal token is not yet valid"
        )
    max_ttl = int(settings.agent_principal_token_max_ttl_seconds)
    if int(exp) - int(iat) > max_ttl:
        raise HTTPException(
            status_code=401, detail="Agent principal token TTL exceeds maximum"
        )
    if not str(payload.get("jti") or "").strip():
        raise HTTPException(status_code=401, detail="Agent principal token missing jti")
    if str(payload.get("kid") or "") != _agent_principal_token_key_id():
        raise HTTPException(
            status_code=401, detail="Unsupported agent principal token key"
        )
    if str(payload.get("aud") or "") != settings.agent_principal_token_audience:
        raise HTTPException(
            status_code=401, detail="Invalid agent principal token audience"
        )
    if str(payload.get("iss") or "") != settings.agent_principal_token_issuer:
        raise HTTPException(status_code=401, detail="Invalid agent principal token issuer")
    return payload


def _agent_principal_token_key_id() -> str:
    return "agent-principal-signing-secret:v1"


def _urlsafe_b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    padding = "=" * ((4 - len(value) % 4) % 4)
    return base64.urlsafe_b64decode((value + padding).encode("utf-8"))


__all__ = [
    "PrincipalContext",
    "agent_principal_token_metadata",
    "build_agent_principal_token",
    "ensure_principal",
    "resolve_principal_context",
]
