"""Recommendation repository hooks."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json
from modules.memory.repositories.clients import DEFAULT_CLIENT_ID, ensure_client


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "client_id": row["client_id"],
        "product_ids": from_json(row["product_ids_json"], default=[]),
        "alignment_score": row["alignment_score"],
        "context": from_json(row["context_json"], default={}),
        "created_at": row["created_at"],
    }


def create_recommendation(
    session_id: str,
    product_ids: List[str],
    alignment_score: float | None = None,
    context: Dict[str, Any] | None = None,
    client_id: str = DEFAULT_CLIENT_ID,
) -> Dict[str, Any]:
    """Create a recommendation record."""
    ensure_client(client_id)
    recommendation_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO recommendations (
            id,
            session_id,
            client_id,
            product_ids_json,
            alignment_score,
            context_json
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            recommendation_id,
            session_id,
            client_id,
            to_json(product_ids),
            alignment_score,
            to_json(context),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)
    ).fetchone()
    return _row_to_dict(row)


def list_recommendations(
    session_id: str,
    limit: int = 20,
    client_id: str = DEFAULT_CLIENT_ID,
) -> List[Dict[str, Any]]:
    """List recommendations for a session."""
    rows = (
        get_connection()
        .execute(
            """
        SELECT * FROM recommendations
        WHERE session_id = ? AND client_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
            (session_id, client_id, limit),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


__all__ = ["create_recommendation", "list_recommendations"]
