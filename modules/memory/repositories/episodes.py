"""Episodic memory repository."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_id": row["session_id"],
        "outcome": row["outcome"],
        "takeaways": from_json(row["takeaways_json"], default=[]),
        "created_at": row["created_at"],
    }


def create_episode(
    user_id: str,
    session_id: str | None,
    outcome: str | None,
    takeaways: List[str] | None = None,
) -> Dict[str, Any]:
    """Create an episode record."""
    episode_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO episodes (id, user_id, session_id, outcome, takeaways_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (episode_id, user_id, session_id, outcome, to_json(takeaways)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    return _row_to_dict(row)


def list_recent(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """List recent episodes for a user."""
    rows = (
        get_connection()
        .execute(
            """
        SELECT * FROM episodes
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
            (user_id, limit),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


def get_latest(user_id: str) -> Optional[Dict[str, Any]]:
    """Get the latest episode for a user."""
    row = (
        get_connection()
        .execute(
            """
        SELECT * FROM episodes
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
            (user_id,),
        )
        .fetchone()
    )
    return _row_to_dict(row) if row else None


__all__ = ["create_episode", "list_recent", "get_latest"]
