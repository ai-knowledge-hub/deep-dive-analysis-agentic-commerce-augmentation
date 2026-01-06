"""Recommendation repository hooks."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from db.connection import get_connection
from .base import from_json, to_json


def create_recommendation(
    session_id: str,
    product_ids: List[str],
    empowering_score: float | None = None,
    context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    recommendation_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO recommendations (id, session_id, product_ids_json, empowering_score, context_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (recommendation_id, session_id, to_json(product_ids), empowering_score, to_json(context)),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM recommendations WHERE id = ?", (recommendation_id,)).fetchone()
    return _row_to_dict(row)


def list_recommendations(session_id: str, limit: int = 20) -> List[Dict[str, Any]]:
    rows = get_connection().execute(
        """
        SELECT * FROM recommendations
        WHERE session_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (session_id, limit),
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "session_id": row["session_id"],
        "product_ids": from_json(row["product_ids_json"], default=[]),
        "empowering_score": row["empowering_score"],
        "context": from_json(row["context_json"], default={}),
        "created_at": row["created_at"],
    }
