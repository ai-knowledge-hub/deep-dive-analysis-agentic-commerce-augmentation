from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.db.core.connection import get_connection


def list_configs() -> list[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute("SELECT * FROM llm_provider_configs ORDER BY provider")
        .fetchall()
    )
    return [_row(row) for row in rows]


def get_config(*, provider: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            "SELECT * FROM llm_provider_configs WHERE provider = ?",
            (provider,),
        )
        .fetchone()
    )
    return _row(row) if row else None


def get_active_provider() -> str | None:
    row = (
        get_connection()
        .execute(
            "SELECT provider FROM llm_provider_configs WHERE is_active = 1 LIMIT 1"
        )
        .fetchone()
    )
    return row["provider"] if row else None


def upsert_config(
    *,
    provider: str,
    api_key: Optional[str] = None,
    validation_api_key: Optional[str] = None,
    model: Optional[str] = None,
    validation_model: Optional[str] = None,
    is_active: Optional[bool] = None,
    updated_by: Optional[str] = None,
) -> Dict[str, Any]:
    conn = get_connection()
    existing = get_config(provider=provider)
    next_active = (
        int(is_active) if is_active is not None else int(existing["is_active"]) if existing else 0
    )
    conn.execute(
        """
        INSERT INTO llm_provider_configs (
            provider,
            api_key,
            validation_api_key,
            model,
            validation_model,
            is_active,
            updated_by
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(provider) DO UPDATE SET
            api_key = excluded.api_key,
            validation_api_key = excluded.validation_api_key,
            model = excluded.model,
            validation_model = excluded.validation_model,
            is_active = excluded.is_active,
            updated_by = excluded.updated_by,
            updated_at = datetime('now')
        """,
        (
            provider,
            api_key,
            validation_api_key,
            model,
            validation_model,
            next_active,
            updated_by,
        ),
    )
    conn.commit()
    return get_config(provider=provider) or {}


def set_active_provider(*, provider: str) -> None:
    conn = get_connection()
    conn.execute("UPDATE llm_provider_configs SET is_active = 0")
    conn.execute(
        "UPDATE llm_provider_configs SET is_active = 1, updated_at = datetime('now') WHERE provider = ?",
        (provider,),
    )
    conn.commit()


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "provider": row["provider"],
        "api_key": row["api_key"],
        "validation_api_key": row["validation_api_key"],
        "model": row["model"],
        "validation_model": row["validation_model"],
        "is_active": bool(row["is_active"]),
        "updated_by": row["updated_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "list_configs",
    "get_config",
    "get_active_provider",
    "upsert_config",
    "set_active_provider",
]
