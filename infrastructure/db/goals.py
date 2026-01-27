"""Goal storage repository (infrastructure canonical)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_goal(
    *,
    user_id: str,
    goal_text: str,
    session_id: str | None,
    domain: str | None,
    importance: float,
    goal_embedding: List[float] | None,
    client_id: str,
    brand_id: str | None,
) -> Dict[str, Any]:
    ensure_client(client_id)
    goal_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO goals (
            id,
            user_id,
            session_id,
            client_id,
            brand_id,
            goal_text,
            goal_embedding,
            domain,
            importance
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            goal_id,
            user_id,
            session_id,
            client_id,
            brand_id,
            goal_text,
            _encode_embedding(goal_embedding),
            domain,
            importance,
        ),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM goals WHERE id = ?", (goal_id,)).fetchone()
    return _row_to_dict(row)


def list_goals_for_session(*, session_id: str, client_id: str) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT * FROM goals
            WHERE session_id = ? AND client_id = ?
            ORDER BY created_at ASC
            """,
            (session_id, client_id),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


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
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "goal_text": row["goal_text"],
        "goal_embedding": _decode_embedding(row["goal_embedding"]),
        "domain": row["domain"],
        "importance": row["importance"],
        "created_at": row["created_at"],
    }


__all__ = ["create_goal", "list_goals_for_session"]

