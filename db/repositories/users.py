"""User repository helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from db.connection import get_connection
from .base import to_json, from_json


def ensure_user(user_id: str) -> None:
    """Create a user row if it doesn't already exist."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO users (id)
        VALUES (?)
        """,
        (user_id,),
    )
    conn.commit()


def update_metadata(user_id: str, preferences: Dict[str, Any] | None = None, metadata: Dict[str, Any] | None = None) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO users (id, preferences_json, metadata_json)
        VALUES (?, json(?), json(?))
        ON CONFLICT(id) DO UPDATE SET
            preferences_json = COALESCE(excluded.preferences_json, users.preferences_json),
            metadata_json = COALESCE(excluded.metadata_json, users.metadata_json)
        """,
        (user_id, to_json(preferences) or to_json({}), to_json(metadata) or to_json({})),
    )
    conn.commit()


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT * FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if not row:
        return None
    return {
        "id": row["id"],
        "created_at": row["created_at"],
        "preferences": from_json(row["preferences_json"], default={}),
        "metadata": from_json(row["metadata_json"], default={}),
    }
