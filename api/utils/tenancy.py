"""Tenant scoping helpers for API routes."""

from __future__ import annotations

from fastapi import HTTPException

from shared.config.env import settings
from shared.db.connection import get_connection
from infrastructure.db.tenancy import DEFAULT_CLIENT_ID


def _admin_ids() -> set[str]:
    raw = settings.admin_user_ids or ""
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_admin(user_id: str | None) -> bool:
    if not user_id:
        return False
    return user_id in _admin_ids()


def require_client_id(client_id: str | None, user_id: str | None) -> str:
    if client_id:
        return client_id
    if is_admin(user_id):
        return DEFAULT_CLIENT_ID
    raise HTTPException(status_code=400, detail="client_id is required")


def require_admin(user_id: str | None) -> None:
    if not is_admin(user_id):
        raise HTTPException(status_code=403, detail="admin access required")


def has_client_role(
    *,
    client_id: str,
    user_id: str | None,
    allowed_roles: set[str],
) -> bool:
    if not user_id:
        return False
    if is_admin(user_id):
        return True
    row = (
        get_connection()
        .execute(
            """
        SELECT role
        FROM client_users
        WHERE client_id = ? AND user_id = ?
        LIMIT 1
        """,
            (client_id, user_id),
        )
        .fetchone()
    )
    if not row:
        return False
    role = str(row["role"] or "").strip().lower()
    return role in {item.strip().lower() for item in allowed_roles if item.strip()}


def require_client_role(
    *,
    client_id: str,
    user_id: str | None,
    allowed_roles: set[str],
) -> None:
    if not has_client_role(
        client_id=client_id, user_id=user_id, allowed_roles=allowed_roles
    ):
        raise HTTPException(status_code=403, detail="insufficient client role")


__all__ = [
    "require_client_id",
    "is_admin",
    "require_admin",
    "has_client_role",
    "require_client_role",
]
