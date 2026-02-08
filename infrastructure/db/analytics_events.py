from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def create_event(
    *,
    client_id: str,
    brand_id: Optional[str],
    product_id: Optional[str],
    variant_id: Optional[str],
    experiment_id: Optional[str],
    event_type: str,
    source: Optional[str],
    event_timestamp: Optional[str],
    metadata: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    event_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO analytics_events (
            id,
            client_id,
            brand_id,
            product_id,
            variant_id,
            experiment_id,
            event_type,
            source,
            event_timestamp,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            event_id,
            client_id,
            brand_id,
            product_id,
            variant_id,
            experiment_id,
            event_type,
            source,
            event_timestamp,
            to_json(metadata or {}),
        ),
    )
    conn.commit()
    return get_event(event_id) or {}


def get_event(event_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM analytics_events WHERE id = ?", (event_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_events(
    *,
    client_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    experiment_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    filters: list[str] = []
    params: list[Any] = []
    if client_id:
        filters.append("client_id = ?")
        params.append(client_id)
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if product_id:
        filters.append("product_id = ?")
        params.append(product_id)
    if experiment_id:
        filters.append("experiment_id = ?")
        params.append(experiment_id)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = conn.execute(
        f"""
        SELECT * FROM analytics_events
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def delete_events_for_experiment(experiment_id: str) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM analytics_events WHERE experiment_id = ?",
        (experiment_id,),
    )
    conn.commit()
    return result.rowcount if result else 0


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "variant_id": row["variant_id"],
        "experiment_id": row["experiment_id"],
        "event_type": row["event_type"],
        "source": row["source"],
        "event_timestamp": row["event_timestamp"],
        "metadata": from_json(row["metadata_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_event",
    "get_event",
    "list_events",
    "delete_events_for_experiment",
]
