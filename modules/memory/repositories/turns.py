"""Conversation turn storage."""

from __future__ import annotations

from typing import Any, Dict, List

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "speaker": row["speaker"],
        "content": row["content"],
        "metadata": from_json(row["metadata_json"], default={}),
        "created_at": row["created_at"],
    }


def add_turn(
    session_id: str,
    speaker: str,
    content: str,
    metadata: dict | None = None,
) -> Dict[str, Any]:
    """Add a conversation turn."""
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT INTO turns (session_id, speaker, content, metadata_json)
        VALUES (?, ?, ?, ?)
        """,
        (session_id, speaker, content, to_json(metadata)),
    )
    conn.commit()
    row_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM turns WHERE id = ?", (row_id,)).fetchone()
    return _row_to_dict(row)


def list_turns(session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """List turns for a session."""
    rows = (
        get_connection()
        .execute(
            """
        SELECT * FROM turns
        WHERE session_id = ?
        ORDER BY created_at ASC
        LIMIT ?
        """,
            (session_id, limit),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


__all__ = ["add_turn", "list_turns"]
