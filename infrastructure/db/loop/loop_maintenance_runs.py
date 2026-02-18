from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.tenancy import ensure_client


def create_run(
    *,
    client_id: str,
    lookback_days: int,
    min_confidence: float,
    calibration_profiles_updated: int,
    memory_artifacts_distilled: int,
    triggered_by: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_client(client_id)
    run_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO loop_maintenance_runs (
            id,
            client_id,
            lookback_days,
            min_confidence,
            calibration_profiles_updated,
            memory_artifacts_distilled,
            triggered_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            client_id,
            lookback_days,
            min_confidence,
            calibration_profiles_updated,
            memory_artifacts_distilled,
            triggered_by,
        ),
    )
    conn.commit()
    return get_run(run_id=run_id) or {}


def get_run(*, run_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM loop_maintenance_runs WHERE id = ?", (run_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_runs(
    *,
    client_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    rows = (
        get_connection()
        .execute(
            """
            SELECT * FROM loop_maintenance_runs
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, max(1, int(limit))),
        )
        .fetchall()
    )
    return [_row(row) for row in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "lookback_days": int(row["lookback_days"] or 0),
        "min_confidence": float(row["min_confidence"] or 0.0),
        "calibration_profiles_updated": int(row["calibration_profiles_updated"] or 0),
        "memory_artifacts_distilled": int(row["memory_artifacts_distilled"] or 0),
        "triggered_by": row["triggered_by"],
        "created_at": row["created_at"],
    }


__all__ = ["create_run", "get_run", "list_runs"]
