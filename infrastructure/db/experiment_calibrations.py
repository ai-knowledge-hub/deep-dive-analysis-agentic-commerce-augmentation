from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def upsert_calibration(
    *,
    brand_id: str,
    client_id: str,
    verified_runs: int,
    accuracy: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    conn = get_connection()
    existing = get_calibration(brand_id=brand_id)
    if existing:
        conn.execute(
            """
            UPDATE experiment_calibrations
            SET verified_runs = ?,
                accuracy = ?,
                metadata_json = json(?),
                last_updated = datetime('now')
            WHERE brand_id = ?
            """,
            (
                verified_runs,
                accuracy,
                to_json(metadata or {}),
                brand_id,
            ),
        )
        conn.commit()
        return get_calibration(brand_id=brand_id) or {}

    calibration_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO experiment_calibrations
            (id, brand_id, client_id, verified_runs, accuracy, metadata_json)
        VALUES (?, ?, ?, ?, ?, json(?))
        """,
        (calibration_id, brand_id, client_id, verified_runs, accuracy, to_json(metadata or {})),
    )
    conn.commit()
    return get_calibration(brand_id=brand_id) or {}


def get_calibration(*, brand_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM experiment_calibrations WHERE brand_id = ?", (brand_id,))
        .fetchone()
    )
    return _row(row) if row else None


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "brand_id": row["brand_id"],
        "client_id": row["client_id"],
        "verified_runs": int(row["verified_runs"] or 0),
        "accuracy": float(row["accuracy"] or 0.0),
        "metadata": from_json(row["metadata_json"], default={}),
        "last_updated": row["last_updated"],
    }


__all__ = ["upsert_calibration", "get_calibration"]
