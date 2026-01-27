"""Episodic memory repository (infrastructure canonical)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_episode(
    *,
    user_id: str,
    session_id: str | None,
    outcome: str | None,
    takeaways: list[str] | None,
    client_id: str,
) -> Dict[str, Any]:
    ensure_client(client_id)
    episode_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO episodes (id, user_id, session_id, client_id, outcome, takeaways_json)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (episode_id, user_id, session_id, client_id, outcome, to_json(takeaways)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM episodes WHERE id = ?", (episode_id,)).fetchone()
    return _row_to_dict(row)


def get_latest(*, user_id: str, client_id: str) -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
        SELECT * FROM episodes
        WHERE user_id = ? AND client_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
            (user_id, client_id),
        )
        .fetchone()
    )
    return _row_to_dict(row) if row else None


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_id": row["session_id"],
        "client_id": row["client_id"],
        "outcome": row["outcome"],
        "takeaways": from_json(row["takeaways_json"], default=[]),
        "created_at": row["created_at"],
    }


__all__ = ["create_episode", "get_latest"]

