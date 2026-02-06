from __future__ import annotations

import uuid
from typing import Any, Dict, List

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def create_recommendation(
    *, experiment_id: str, recommendation: Dict[str, Any]
) -> Dict[str, Any]:
    rec_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_recommendations
            (id, experiment_id, recommendation_json)
        VALUES (?, ?, json(?))
        """,
        (rec_id, experiment_id, to_json(recommendation) or to_json({})),
    )
    conn.commit()
    return get_recommendation(rec_id) or {}


def get_recommendation(rec_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            "SELECT * FROM experiment_recommendations WHERE id = ?",
            (rec_id,),
        )
        .fetchone()
    )
    return _row(row) if row else None


def list_recommendations(
    *, experiment_id: str, limit: int = 50
) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT * FROM experiment_recommendations
            WHERE experiment_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (experiment_id, limit),
        )
        .fetchall()
    )
    return [_row(row) for row in rows]


def delete_recommendations_for_experiment(experiment_id: str) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM experiment_recommendations WHERE experiment_id = ?",
        (experiment_id,),
    )
    conn.commit()
    return result.rowcount if result else 0


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "recommendation": from_json(row["recommendation_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_recommendation",
    "get_recommendation",
    "list_recommendations",
    "delete_recommendations_for_experiment",
]
