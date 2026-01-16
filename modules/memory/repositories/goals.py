"""Goal storage repository."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json


def _decode_embedding(value: bytes | str | None) -> List[float] | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        value = value.decode("utf-8")
    return from_json(value, default=None)


def _encode_embedding(embedding: List[float] | None) -> str | None:
    if embedding is None:
        return None
    return to_json(embedding)


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_id": row["session_id"],
        "goal_text": row["goal_text"],
        "goal_embedding": _decode_embedding(row["goal_embedding"]),
        "domain": row["domain"],
        "importance": row["importance"],
        "created_at": row["created_at"],
    }


def create_goal(
    user_id: str,
    goal_text: str,
    session_id: str | None = None,
    domain: str | None = None,
    importance: float = 0.5,
    goal_embedding: List[float] | None = None,
) -> Dict[str, Any]:
    """Create a new goal."""
    goal_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO goals (id, user_id, session_id, goal_text, goal_embedding, domain, importance)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            goal_id,
            user_id,
            session_id,
            goal_text,
            _encode_embedding(goal_embedding),
            domain,
            importance,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return _row_to_dict(row)


def list_goals(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """List goals for a user."""
    rows = (
        get_connection()
        .execute(
            """
        SELECT * FROM goals
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
            (user_id, limit),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


def list_goals_for_session(session_id: str) -> List[Dict[str, Any]]:
    """List goals for a session."""
    rows = (
        get_connection()
        .execute(
            "SELECT * FROM goals WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


def delete_goal(goal_id: str) -> None:
    """Delete a goal."""
    conn = get_connection()
    conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    conn.commit()


def get_goal(goal_id: str) -> Optional[Dict[str, Any]]:
    """Get a goal by ID."""
    row = (
        get_connection()
        .execute("SELECT * FROM goals WHERE id = ?", (goal_id,))
        .fetchone()
    )
    return _row_to_dict(row) if row else None


__all__ = [
    "create_goal",
    "list_goals",
    "list_goals_for_session",
    "delete_goal",
    "get_goal",
]
