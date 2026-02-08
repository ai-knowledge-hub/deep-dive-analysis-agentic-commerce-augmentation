from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def get_calibration_profile(
    *,
    client_id: str,
    provider: str,
    brand_id: Optional[str] = None,
) -> Dict[str, Any] | None:
    ensure_client(client_id)
    conn = get_connection()
    if brand_id is None:
        row = conn.execute(
            """
            SELECT * FROM calibration_profiles
            WHERE client_id = ? AND brand_id IS NULL AND provider = ?
            LIMIT 1
            """,
            (client_id, provider),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM calibration_profiles
            WHERE client_id = ? AND brand_id = ? AND provider = ?
            LIMIT 1
            """,
            (client_id, brand_id, provider),
        ).fetchone()
    return _row(row) if row else None


def upsert_calibration_profile(
    *,
    client_id: str,
    provider: str,
    metric_weights: Optional[Dict[str, Any]] = None,
    drift_score: Optional[float] = None,
    brand_id: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_client(client_id)
    existing = get_calibration_profile(
        client_id=client_id, brand_id=brand_id, provider=provider
    )
    conn = get_connection()
    if existing:
        conn.execute(
            """
            UPDATE calibration_profiles
            SET metric_weights_json = json(?),
                drift_score = ?,
                updated_at = datetime('now')
            WHERE id = ?
            """,
            (
                to_json(metric_weights or {}),
                drift_score if drift_score is not None else existing.get("drift_score", 0.0),
                existing["id"],
            ),
        )
        conn.commit()
        return get_calibration_profile(
            client_id=client_id, brand_id=brand_id, provider=provider
        ) or {}

    profile_id = str(uuid.uuid4())
    conn.execute(
        """
        INSERT INTO calibration_profiles (
            id,
            client_id,
            brand_id,
            provider,
            metric_weights_json,
            drift_score
        )
        VALUES (?, ?, ?, ?, json(?), ?)
        """,
        (
            profile_id,
            client_id,
            brand_id,
            provider,
            to_json(metric_weights or {}),
            drift_score if drift_score is not None else 0.0,
        ),
    )
    conn.commit()
    return get_calibration_profile(
        client_id=client_id, brand_id=brand_id, provider=provider
    ) or {}


def list_calibration_profiles(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    provider: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    conn = get_connection()
    filters = ["client_id = ?"]
    params: list[Any] = [client_id]
    if brand_id is not None:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if provider:
        filters.append("provider = ?")
        params.append(provider)
    where = f"WHERE {' AND '.join(filters)}"
    rows = conn.execute(
        f"""
        SELECT * FROM calibration_profiles
        {where}
        ORDER BY updated_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "provider": row["provider"],
        "metric_weights": from_json(row["metric_weights_json"], default={}),
        "drift_score": float(row["drift_score"] or 0.0),
        "updated_at": row["updated_at"],
        "created_at": row["created_at"],
    }


__all__ = [
    "get_calibration_profile",
    "upsert_calibration_profile",
    "list_calibration_profiles",
]

