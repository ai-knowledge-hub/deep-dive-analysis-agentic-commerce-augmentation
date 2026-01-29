from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_battery(
    *,
    client_id: str,
    product_id: str,
    name: str,
    purpose: Optional[str] = None,
    generation_mode: Optional[str] = None,
    status: str = "draft",
    brand_id: Optional[str] = None,
) -> Dict[str, Any]:
    battery_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO query_batteries
            (id, client_id, brand_id, product_id, name, purpose, generation_mode, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            battery_id,
            client_id,
            brand_id,
            product_id,
            name,
            purpose,
            generation_mode,
            status,
        ),
    )
    conn.commit()
    return get_battery(battery_id) or {}


def get_battery(battery_id: str, *, client_id: str | None = None) -> Dict[str, Any] | None:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            "SELECT * FROM query_batteries WHERE id = ? AND client_id = ?",
            (battery_id, client_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM query_batteries WHERE id = ?",
            (battery_id,),
        ).fetchone()
    return _battery_row(row) if row else None


def list_batteries(
    *,
    client_id: str,
    product_id: str | None = None,
    brand_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    query = """
        SELECT * FROM query_batteries
        WHERE client_id = ?
    """
    params: list[Any] = [client_id]
    if product_id:
        query += " AND product_id = ?"
        params.append(product_id)
    if brand_id:
        query += " AND brand_id = ?"
        params.append(brand_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_battery_row(row) for row in rows]


def update_battery(
    *,
    battery_id: str,
    client_id: str,
    name: Optional[str] = None,
    purpose: Optional[str] = None,
    generation_mode: Optional[str] = None,
    status: Optional[str] = None,
) -> Dict[str, Any] | None:
    conn = get_connection()
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if purpose is not None:
        updates.append("purpose = ?")
        params.append(purpose)
    if generation_mode is not None:
        updates.append("generation_mode = ?")
        params.append(generation_mode)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if not updates:
        return get_battery(battery_id, client_id=client_id)
    updates.append("updated_at = datetime('now')")
    params.extend([battery_id, client_id])
    conn.execute(
        f"""
        UPDATE query_batteries
        SET {", ".join(updates)}
        WHERE id = ? AND client_id = ?
        """,
        params,
    )
    conn.commit()
    return get_battery(battery_id, client_id=client_id)


def add_query(
    *,
    battery_id: str,
    query_text: str,
    query_type: Optional[str] = None,
    intent_archetype: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None,
    weight: float = 1.0,
    enabled: bool = True,
) -> Dict[str, Any]:
    query_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO query_battery_queries
            (id, battery_id, query_text, query_type, intent_archetype, constraints_json, weight, enabled)
        VALUES (?, ?, ?, ?, ?, json(?), ?, ?)
        """,
        (
            query_id,
            battery_id,
            query_text,
            query_type,
            intent_archetype,
            to_json(constraints) or to_json({}),
            weight,
            1 if enabled else 0,
        ),
    )
    conn.commit()
    return get_query(query_id) or {}


def get_query(query_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM query_battery_queries WHERE id = ?", (query_id,))
        .fetchone()
    )
    return _query_row(row) if row else None


def list_queries(battery_id: str) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT * FROM query_battery_queries
            WHERE battery_id = ?
            ORDER BY created_at ASC
            """,
            (battery_id,),
        )
        .fetchall()
    )
    return [_query_row(row) for row in rows]


def update_query(
    *,
    query_id: str,
    query_text: Optional[str] = None,
    query_type: Optional[str] = None,
    intent_archetype: Optional[str] = None,
    constraints: Optional[Dict[str, Any]] = None,
    weight: Optional[float] = None,
    enabled: Optional[bool] = None,
) -> Dict[str, Any] | None:
    conn = get_connection()
    updates: list[str] = []
    params: list[Any] = []
    if query_text is not None:
        updates.append("query_text = ?")
        params.append(query_text)
    if query_type is not None:
        updates.append("query_type = ?")
        params.append(query_type)
    if intent_archetype is not None:
        updates.append("intent_archetype = ?")
        params.append(intent_archetype)
    if constraints is not None:
        updates.append("constraints_json = json(?)")
        params.append(to_json(constraints) or to_json({}))
    if weight is not None:
        updates.append("weight = ?")
        params.append(weight)
    if enabled is not None:
        updates.append("enabled = ?")
        params.append(1 if enabled else 0)
    if not updates:
        return get_query(query_id)
    params.append(query_id)
    conn.execute(
        f"""
        UPDATE query_battery_queries
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        params,
    )
    conn.commit()
    return get_query(query_id)


def _battery_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "name": row["name"],
        "purpose": row["purpose"],
        "generation_mode": row["generation_mode"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _query_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "battery_id": row["battery_id"],
        "query_text": row["query_text"],
        "query_type": row["query_type"],
        "intent_archetype": row["intent_archetype"],
        "constraints": from_json(row["constraints_json"], default={}),
        "weight": row["weight"],
        "enabled": bool(row["enabled"]),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_battery",
    "get_battery",
    "list_batteries",
    "update_battery",
    "add_query",
    "get_query",
    "list_queries",
    "update_query",
]
