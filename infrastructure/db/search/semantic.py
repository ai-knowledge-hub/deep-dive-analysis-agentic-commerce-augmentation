"""Semantic memory repository (infrastructure canonical)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import DEFAULT_CLIENT_ID, ensure_client
from infrastructure.db.search.users import ensure_user

DEFAULT_USER_ID = "__default__"


def upsert_entry(
    *,
    key: str,
    value: Any,
    user_id: str = DEFAULT_USER_ID,
    client_id: str = DEFAULT_CLIENT_ID,
    embedding: bytes | None = None,
) -> Dict[str, Any]:
    conn = get_connection()
    ensure_user(user_id)
    ensure_client(client_id)
    conn.execute(
        """
        INSERT INTO semantic_memory (id, user_id, client_id, key, value_json, embedding, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(client_id, user_id, key)
        DO UPDATE SET
            value_json = excluded.value_json,
            embedding = COALESCE(excluded.embedding, semantic_memory.embedding),
            updated_at = datetime('now')
        """,
        (str(uuid.uuid4()), user_id, client_id, key, to_json(value), embedding),
    )
    conn.commit()
    return get_entry(key=key, user_id=user_id, client_id=client_id) or {}


def get_entry(
    *,
    key: str,
    user_id: str = DEFAULT_USER_ID,
    client_id: str = DEFAULT_CLIENT_ID,
) -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
        SELECT * FROM semantic_memory
        WHERE user_id = ? AND client_id = ? AND key = ?
        """,
            (user_id, client_id, key),
        )
        .fetchone()
    )
    return _row_to_dict(row) if row else None


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "client_id": row["client_id"],
        "key": row["key"],
        "value": from_json(row["value_json"], default=None),
        "embedding": row["embedding"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }

def list_entries(
    *, user_id: str = DEFAULT_USER_ID, client_id: str = DEFAULT_CLIENT_ID
) -> list[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            "SELECT * FROM semantic_memory WHERE user_id = ? AND client_id = ? ORDER BY updated_at DESC",
            (user_id, client_id),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


def delete_entry(*, key: str, user_id: str = DEFAULT_USER_ID, client_id: str = DEFAULT_CLIENT_ID) -> None:
    conn = get_connection()
    conn.execute(
        "DELETE FROM semantic_memory WHERE user_id = ? AND client_id = ? AND key = ?",
        (user_id, client_id, key),
    )
    conn.commit()


__all__ = [
    "DEFAULT_USER_ID",
    "DEFAULT_CLIENT_ID",
    "upsert_entry",
    "get_entry",
    "list_entries",
    "delete_entry",
]
