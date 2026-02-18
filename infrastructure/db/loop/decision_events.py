from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.tenancy import ensure_client


def create_decision_event(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    policy_action: str,
    uncertainty: Optional[float] = None,
    expected_gain: Optional[float] = None,
    selected_reason: Optional[str] = None,
) -> Dict[str, Any]:
    event_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO decision_events (
            id,
            client_id,
            brand_id,
            product_id,
            policy_action,
            uncertainty,
            expected_gain,
            selected_reason
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            client_id,
            brand_id,
            product_id,
            policy_action,
            uncertainty,
            expected_gain,
            selected_reason,
        ),
    )
    conn.commit()
    return get_decision_event(event_id=event_id) or {}


def get_decision_event(*, event_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM decision_events WHERE id = ?", (event_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_decision_events(
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
        SELECT * FROM decision_events
        {where}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def get_latest_decision_event(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
) -> Dict[str, Any] | None:
    events = list_decision_events(
        client_id=client_id,
        brand_id=brand_id,
        product_id=product_id,
        limit=1,
    )
    return events[0] if events else None


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "policy_action": row["policy_action"],
        "uncertainty": row["uncertainty"],
        "expected_gain": row["expected_gain"],
        "selected_reason": row["selected_reason"],
        "created_at": row["created_at"],
    }


__all__ = [
    "create_decision_event",
    "get_decision_event",
    "list_decision_events",
    "get_latest_decision_event",
]

