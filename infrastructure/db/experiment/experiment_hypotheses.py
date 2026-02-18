from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def create_hypothesis(
    *,
    experiment_id: str,
    snapshot_version: int,
    statement: Dict[str, Any],
    status: str = "active",
    source: str = "retrieval_gap",
) -> Dict[str, Any]:
    hypothesis_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_hypotheses
            (id, experiment_id, snapshot_version, statement_json, status, source)
        VALUES (?, ?, ?, json(?), ?, ?)
        """,
        (
            hypothesis_id,
            experiment_id,
            snapshot_version,
            to_json(statement) or to_json({}),
            status,
            source,
        ),
    )
    conn.commit()
    return get_hypothesis(hypothesis_id=hypothesis_id) or {}


def get_hypothesis(*, hypothesis_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM experiment_hypotheses WHERE id = ?", (hypothesis_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_hypotheses(
    *,
    experiment_id: str,
    snapshot_version: Optional[int] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    query = "SELECT * FROM experiment_hypotheses WHERE experiment_id = ?"
    params: list[Any] = [experiment_id]
    if snapshot_version is not None:
        query += " AND snapshot_version = ?"
        params.append(snapshot_version)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = get_connection().execute(query, params).fetchall()
    return [_row(row) for row in rows]


def count_hypotheses(*, experiment_id: str, snapshot_version: Optional[int] = None) -> int:
    if snapshot_version is None:
        row = (
            get_connection()
            .execute(
                "SELECT COUNT(*) AS count FROM experiment_hypotheses WHERE experiment_id = ?",
                (experiment_id,),
            )
            .fetchone()
        )
    else:
        row = (
            get_connection()
            .execute(
                """
                SELECT COUNT(*) AS count FROM experiment_hypotheses
                WHERE experiment_id = ? AND snapshot_version = ?
                """,
                (experiment_id, snapshot_version),
            )
            .fetchone()
        )
    return int((row or {"count": 0})["count"])


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "snapshot_version": int(row["snapshot_version"] or 0),
        "statement": from_json(row["statement_json"], default={}),
        "status": row["status"],
        "source": row["source"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_hypothesis",
    "get_hypothesis",
    "list_hypotheses",
    "count_hypotheses",
]
