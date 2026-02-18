from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_world_state_snapshot(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    vertical: Optional[str] = None,
    state: Optional[Dict[str, Any]] = None,
    version: int = 1,
) -> Dict[str, Any]:
    snapshot_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO world_states (
            id,
            client_id,
            brand_id,
            product_id,
            vertical,
            state_json,
            version
        )
        VALUES (?, ?, ?, ?, ?, json(?), ?)
        """,
        (
            snapshot_id,
            client_id,
            brand_id,
            product_id,
            vertical,
            to_json(state) or to_json({}),
            version,
        ),
    )
    conn.commit()
    return get_world_state(snapshot_id=snapshot_id) or {}


def get_world_state(*, snapshot_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM world_states WHERE id = ?", (snapshot_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_world_states(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    conn = get_connection()
    filters = ["client_id = ?"]
    params: list[Any] = [client_id]
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if product_id:
        filters.append("product_id = ?")
        params.append(product_id)
    where = f"WHERE {' AND '.join(filters)}"
    rows = conn.execute(
        f"""
        SELECT * FROM world_states
        {where}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def get_latest_world_state(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Dict[str, Any] | None:
    rows = list_world_states(
        client_id=client_id,
        brand_id=brand_id,
        product_id=product_id,
        limit=1,
    )
    return rows[0] if rows else None


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "vertical": row["vertical"],
        "state": from_json(row["state_json"], default={}),
        "version": row["version"],
        "created_at": row["created_at"],
    }


__all__ = [
    "create_world_state_snapshot",
    "get_world_state",
    "list_world_states",
    "get_latest_world_state",
]

