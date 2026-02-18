"""Recommendation repository hooks (infrastructure canonical)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_recommendation(
    *,
    session_id: str,
    product_ids: List[str],
    alignment_score: float | None,
    context: Dict[str, Any],
    client_id: str,
) -> Dict[str, Any]:
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


__all__ = ["create_recommendation"]

