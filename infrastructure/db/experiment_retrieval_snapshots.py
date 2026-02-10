from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def create_snapshot(
    *,
    experiment_id: str,
    battery_id: str,
    query_id: str,
    snapshot_version: int,
    retrieval: Dict[str, Any],
) -> Dict[str, Any]:
    snapshot_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_retrieval_snapshots
            (id, experiment_id, battery_id, query_id, snapshot_version, retrieval_json)
        VALUES (?, ?, ?, ?, ?, json(?))
        """,
        (
            snapshot_id,
            experiment_id,
            battery_id,
            query_id,
            snapshot_version,
            to_json(retrieval) or to_json({}),
        ),
    )
    conn.commit()
    return get_snapshot(snapshot_id=snapshot_id) or {}


def get_snapshot(*, snapshot_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            "SELECT * FROM experiment_retrieval_snapshots WHERE id = ?",
            (snapshot_id,),
        )
        .fetchone()
    )
    return _row(row) if row else None


def get_snapshot_for_query(
    *,
    experiment_id: str,
    query_id: str,
    snapshot_version: int,
) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT * FROM experiment_retrieval_snapshots
            WHERE experiment_id = ? AND query_id = ? AND snapshot_version = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (experiment_id, query_id, snapshot_version),
        )
        .fetchone()
    )
    return _row(row) if row else None


def list_snapshots(
    *,
    experiment_id: str,
    snapshot_version: Optional[int] = None,
    limit: int = 2000,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    if snapshot_version is None:
        rows = conn.execute(
            """
            SELECT * FROM experiment_retrieval_snapshots
            WHERE experiment_id = ?
            ORDER BY snapshot_version DESC, created_at DESC
            LIMIT ?
            """,
            (experiment_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM experiment_retrieval_snapshots
            WHERE experiment_id = ? AND snapshot_version = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (experiment_id, snapshot_version, limit),
        ).fetchall()
    return [_row(row) for row in rows]


def count_snapshots(
    *,
    experiment_id: str,
    snapshot_version: Optional[int] = None,
) -> int:
    conn = get_connection()
    if snapshot_version is None:
        row = conn.execute(
            "SELECT COUNT(*) AS count FROM experiment_retrieval_snapshots WHERE experiment_id = ?",
            (experiment_id,),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT COUNT(*) AS count FROM experiment_retrieval_snapshots
            WHERE experiment_id = ? AND snapshot_version = ?
            """,
            (experiment_id, snapshot_version),
        ).fetchone()
    return int((row or {"count": 0})["count"])


def latest_snapshot_version(*, experiment_id: str) -> int:
    row = (
        get_connection()
        .execute(
            """
            SELECT MAX(snapshot_version) AS version
            FROM experiment_retrieval_snapshots
            WHERE experiment_id = ?
            """,
            (experiment_id,),
        )
        .fetchone()
    )
    return int((row or {"version": 0})["version"] or 0)


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "battery_id": row["battery_id"],
        "query_id": row["query_id"],
        "snapshot_version": int(row["snapshot_version"] or 0),
        "retrieval": from_json(row["retrieval_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_snapshot",
    "get_snapshot",
    "get_snapshot_for_query",
    "list_snapshots",
    "count_snapshots",
    "latest_snapshot_version",
]
