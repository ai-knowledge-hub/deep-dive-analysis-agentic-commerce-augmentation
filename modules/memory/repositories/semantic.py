"""Semantic memory repository backed by SQLite."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json

DEFAULT_USER_ID = "__default__"


def _ensure_user(user_id: str) -> None:
    """Ensure user exists in the database."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO users (id)
        VALUES (?)
        """,
        (user_id,),
    )
    conn.commit()


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "key": row["key"],
        "value": from_json(row["value_json"], default=None),
        "embedding": row["embedding"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def upsert_entry(
    key: str,
    value: Any,
    user_id: str = DEFAULT_USER_ID,
    embedding: bytes | None = None,
) -> Dict[str, Any]:
    """Create or update a semantic memory record."""
    conn = get_connection()
    _ensure_user(user_id)
    conn.execute(
        """
        INSERT INTO semantic_memory (id, user_id, key, value_json, embedding, updated_at)
        VALUES (?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(user_id, key)
        DO UPDATE SET
            value_json = excluded.value_json,
            embedding = COALESCE(excluded.embedding, semantic_memory.embedding),
            updated_at = datetime('now')
        """,
        (str(uuid.uuid4()), user_id, key, to_json(value), embedding),
    )
    conn.commit()
    return get_entry(key, user_id) or {}


def get_entry(key: str, user_id: str = DEFAULT_USER_ID) -> Optional[Dict[str, Any]]:
    """Get a semantic memory entry by key."""
    row = get_connection().execute(
        """
        SELECT * FROM semantic_memory
        WHERE user_id = ? AND key = ?
        """,
        (user_id, key),
    ).fetchone()
    return _row_to_dict(row) if row else None


def delete_entry(key: str, user_id: str = DEFAULT_USER_ID) -> None:
    """Delete a semantic memory entry."""
    conn = get_connection()
    conn.execute(
        "DELETE FROM semantic_memory WHERE user_id = ? AND key = ?",
        (user_id, key),
    )
    conn.commit()


def list_entries(user_id: str = DEFAULT_USER_ID) -> List[Dict[str, Any]]:
    """List all semantic memory entries for a user."""
    rows = get_connection().execute(
        """
        SELECT * FROM semantic_memory
        WHERE user_id = ?
        ORDER BY updated_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


__all__ = ["DEFAULT_USER_ID", "upsert_entry", "get_entry", "delete_entry", "list_entries"]
