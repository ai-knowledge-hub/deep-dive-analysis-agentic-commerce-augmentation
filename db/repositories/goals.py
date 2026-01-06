"""Goal storage repository."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from db.connection import get_connection


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_id": row["session_id"],
        "goal_text": row["goal_text"],
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
) -> Dict[str, Any]:
    goal_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO goals (id, user_id, session_id, goal_text, domain, importance)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (goal_id, user_id, session_id, goal_text, domain, importance),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return _row_to_dict(row)


def list_goals(user_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    rows = get_connection().execute(
        """
        SELECT * FROM goals
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (user_id, limit),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_goals_for_session(session_id: str) -> List[Dict[str, Any]]:
    rows = get_connection().execute(
        "SELECT * FROM goals WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_goal(goal_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM goals WHERE id = ?", (goal_id,))
    conn.commit()


def get_goal(goal_id: str) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT * FROM goals WHERE id = ?", (goal_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None
