from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_memory_artifact(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    vertical: Optional[str] = None,
    artifact_type: str,
    payload: Dict[str, Any],
    quality_score: float = 0.0,
    support_count: int = 0,
    source: Optional[str] = None,
) -> Dict[str, Any]:
    artifact_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO memory_artifacts (
            id,
            client_id,
            brand_id,
            product_id,
            vertical,
            artifact_type,
            payload_json,
            quality_score,
            support_count,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?, json(?), ?, ?, ?)
        """,
        (
            artifact_id,
            client_id,
            brand_id,
            product_id,
            vertical,
            artifact_type,
            to_json(payload) or to_json({}),
            quality_score,
            support_count,
            source,
        ),
    )
    conn.commit()
    return get_memory_artifact(artifact_id=artifact_id) or {}


def get_memory_artifact(*, artifact_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM memory_artifacts WHERE id = ?", (artifact_id,))
        .fetchone()
    )
    return _row(row) if row else None


def update_memory_artifact_score(
    *,
    artifact_id: str,
    quality_score: Optional[float] = None,
    support_count: Optional[int] = None,
) -> Dict[str, Any] | None:
    updates: list[str] = ["updated_at = datetime('now')"]
    params: list[Any] = []
    if quality_score is not None:
        updates.append("quality_score = ?")
        params.append(quality_score)
    if support_count is not None:
        updates.append("support_count = ?")
        params.append(support_count)
    if len(updates) == 1:
        return get_memory_artifact(artifact_id=artifact_id)
    params.append(artifact_id)
    conn = get_connection()
    conn.execute(
        f"UPDATE memory_artifacts SET {', '.join(updates)} WHERE id = ?",
        params,
    )
    conn.commit()
    return get_memory_artifact(artifact_id=artifact_id)


def mark_memory_artifact_used(*, artifact_id: str) -> Dict[str, Any] | None:
    conn = get_connection()
    conn.execute(
        """
        UPDATE memory_artifacts
        SET last_used_at = datetime('now'),
            support_count = support_count + 1,
            updated_at = datetime('now')
        WHERE id = ?
        """,
        (artifact_id,),
    )
    conn.commit()
    return get_memory_artifact(artifact_id=artifact_id)


def list_memory_artifacts(
    *,
    client_id: str,
    artifact_type: Optional[str] = None,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    vertical: Optional[str] = None,
    min_quality: Optional[float] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    conn = get_connection()
    filters = ["client_id = ?"]
    params: list[Any] = [client_id]
    if artifact_type:
        filters.append("artifact_type = ?")
        params.append(artifact_type)
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if product_id:
        filters.append("product_id = ?")
        params.append(product_id)
    if vertical:
        filters.append("vertical = ?")
        params.append(vertical)
    if min_quality is not None:
        filters.append("quality_score >= ?")
        params.append(min_quality)
    where = f"WHERE {' AND '.join(filters)}"
    rows = conn.execute(
        f"""
        SELECT * FROM memory_artifacts
        {where}
        ORDER BY quality_score DESC, support_count DESC, created_at DESC
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
        "product_id": row["product_id"],
        "vertical": row["vertical"],
        "artifact_type": row["artifact_type"],
        "payload": from_json(row["payload_json"], default={}),
        "quality_score": row["quality_score"],
        "support_count": row["support_count"],
        "source": row["source"],
        "last_used_at": row["last_used_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_memory_artifact",
    "get_memory_artifact",
    "update_memory_artifact_score",
    "mark_memory_artifact_used",
    "list_memory_artifacts",
]

