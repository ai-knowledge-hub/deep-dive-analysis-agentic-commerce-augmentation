"""Session persistence for conversations (infrastructure canonical)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_session(
    *,
    user_id: str | None = None,
    state: dict | None = None,
    client_id: str,
    brand_id: str | None = None,
) -> Dict[str, Any]:
    ensure_client(client_id)
    session_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO sessions (id, user_id, client_id, brand_id, state_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (session_id, user_id, client_id, brand_id, to_json(state) or to_json({})),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _row_to_dict(row)


def get_session(*, session_id: str, client_id: str | None = None) -> Optional[Dict[str, Any]]:
    if client_id:
        row = (
            get_connection()
            .execute(
                "SELECT * FROM sessions WHERE id = ? AND client_id = ?",
                (session_id, client_id),
            )
            .fetchone()
        )
    else:
        row = (
            get_connection()
            .execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            .fetchone()
        )
    return _row_to_dict(row) if row else None


def update_state(*, session_id: str, state: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE sessions SET state_json = ? WHERE id = ?",
        (to_json(state), session_id),
    )
    conn.commit()


def list_sessions(
    *,
    client_id: str,
    user_id: str | None = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    conn = get_connection()
    if user_id:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE user_id = ? AND client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, client_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM sessions
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def delete_session(*, session_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    conn.commit()


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "created_at": row["created_at"],
        "state": from_json(row["state_json"], default={}),
    }


__all__ = [
    "create_session",
    "get_session",
    "update_state",
    "list_sessions",
    "delete_session",
]

