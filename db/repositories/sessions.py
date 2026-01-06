"""Session persistence for Gemini conversations."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from db.connection import get_connection
from .base import from_json, to_json


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "created_at": row["created_at"],
        "state": from_json(row["state_json"], default={}),
    }


def create_session(user_id: str | None = None, state: dict | None = None) -> Dict[str, Any]:
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO sessions (id, user_id, state_json)
        VALUES (?, ?, ?)
        """,
        (session_id, user_id, to_json(state) or to_json({})),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    row = get_connection().execute(
        "SELECT * FROM sessions WHERE id = ?", (session_id,)
    ).fetchone()
    return _row_to_dict(row) if row else None


def update_state(session_id: str, state: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET state_json = ? WHERE id = ?",
        (to_json(state), session_id),
    )
    conn.commit()


def list_sessions(user_id: str | None = None, limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_connection()
    if user_id:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]
