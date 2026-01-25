"""Tenant scoping helpers for API routes."""

from __future__ import annotations

from fastapi import HTTPException

from shared.config.env import settings
from modules.memory.repositories.clients import DEFAULT_CLIENT_ID


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


__all__ = ["require_client_id", "is_admin"]
