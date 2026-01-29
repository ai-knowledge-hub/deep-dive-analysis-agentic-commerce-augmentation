from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_experiment(
    *,
    client_id: str,
    product_id: str,
    name: str,
    battery_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    hypothesis: Optional[Dict[str, Any]] = None,
    competitor_policy: Optional[Dict[str, Any]] = None,
    status: str = "draft",
) -> Dict[str, Any]:
    experiment_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiments
            (id, client_id, brand_id, product_id, battery_id, name, hypothesis_json, competitor_policy_json, status)
        VALUES (?, ?, ?, ?, ?, ?, json(?), json(?), ?)
        """,
        (
            experiment_id,
            client_id,
            brand_id,
            product_id,
            battery_id,
            name,
            to_json(hypothesis) or to_json({}),
            to_json(competitor_policy) or to_json({}),
            status,
        ),
    )
    conn.commit()
    return get_experiment(experiment_id) or {}


def get_experiment(experiment_id: str, *, client_id: str | None = None) -> Dict[str, Any] | None:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ? AND client_id = ?",
            (experiment_id, client_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = ?",
            (experiment_id,),
        ).fetchone()
    return _experiment_row(row) if row else None


def list_experiments(
    *,
    client_id: str,
    product_id: str | None = None,
    brand_id: str | None = None,
    battery_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    query = """
        SELECT * FROM experiments
        WHERE client_id = ?
    """
    params: list[Any] = [client_id]
    if product_id:
        query += " AND product_id = ?"
        params.append(product_id)
    if brand_id:
        query += " AND brand_id = ?"
        params.append(brand_id)
    if battery_id:
        query += " AND battery_id = ?"
        params.append(battery_id)
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_experiment_row(row) for row in rows]


def update_experiment(
    *,
    experiment_id: str,
    client_id: str,
    name: Optional[str] = None,
    status: Optional[str] = None,
    hypothesis: Optional[Dict[str, Any]] = None,
    competitor_policy: Optional[Dict[str, Any]] = None,
    schedule_enabled: Optional[bool] = None,
    schedule_interval_minutes: Optional[int] = None,
    last_run_at: Optional[str] = None,
    next_run_at: Optional[str] = None,
) -> Dict[str, Any] | None:
    conn = get_connection()
    updates: list[str] = []
    params: list[Any] = []
    if name is not None:
        updates.append("name = ?")
        params.append(name)
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if hypothesis is not None:
        updates.append("hypothesis_json = json(?)")
        params.append(to_json(hypothesis) or to_json({}))
    if competitor_policy is not None:
        updates.append("competitor_policy_json = json(?)")
        params.append(to_json(competitor_policy) or to_json({}))
    if schedule_enabled is not None:
        updates.append("schedule_enabled = ?")
        params.append(1 if schedule_enabled else 0)
    if schedule_interval_minutes is not None:
        updates.append("schedule_interval_minutes = ?")
        params.append(schedule_interval_minutes)
    if last_run_at is not None:
        updates.append("last_run_at = ?")
        params.append(last_run_at)
    if next_run_at is not None:
        updates.append("next_run_at = ?")
        params.append(next_run_at)
    if not updates:
        return get_experiment(experiment_id, client_id=client_id)
    updates.append("updated_at = datetime('now')")
    params.extend([experiment_id, client_id])
    conn.execute(
        f"""
        UPDATE experiments
        SET {", ".join(updates)}
        WHERE id = ? AND client_id = ?
        """,
        params,
    )
    conn.commit()
    return get_experiment(experiment_id, client_id=client_id)


def add_variant(
    *,
    experiment_id: str,
    label: str,
    variant_type: str,
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    variant_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_variants
            (id, experiment_id, label, type, payload_json)
        VALUES (?, ?, ?, ?, json(?))
        """,
        (
            variant_id,
            experiment_id,
            label,
            variant_type,
            to_json(payload) or to_json({}),
        ),
    )
    conn.commit()
    return get_variant(variant_id) or {}


def get_variant(variant_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM experiment_variants WHERE id = ?", (variant_id,))
        .fetchone()
    )
    return _variant_row(row) if row else None


def list_variants(experiment_id: str) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT * FROM experiment_variants
            WHERE experiment_id = ?
            ORDER BY created_at ASC
            """,
            (experiment_id,),
        )
        .fetchall()
    )
    return [_variant_row(row) for row in rows]


def list_due_experiments(
    *, client_id: Optional[str] = None, limit: int = 20
) -> List[Dict[str, Any]]:
    conn = get_connection()
    query = """
        SELECT * FROM experiments
        WHERE schedule_enabled = 1
          AND next_run_at IS NOT NULL
          AND next_run_at <= datetime('now')
    """
    params: list[Any] = []
    if client_id:
        query += " AND client_id = ?"
        params.append(client_id)
    query += " ORDER BY next_run_at ASC LIMIT ?"
    params.append(limit)
    rows = conn.execute(query, params).fetchall()
    return [_experiment_row(row) for row in rows]


def _experiment_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "battery_id": row["battery_id"],
        "name": row["name"],
        "hypothesis": from_json(row["hypothesis_json"], default={}),
        "competitor_policy": from_json(row["competitor_policy_json"], default={}),
        "status": row["status"],
        "schedule_enabled": bool(row["schedule_enabled"])
        if row["schedule_enabled"] is not None
        else False,
        "schedule_interval_minutes": row["schedule_interval_minutes"],
        "last_run_at": row["last_run_at"],
        "next_run_at": row["next_run_at"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _variant_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "label": row["label"],
        "type": row["type"],
        "payload": from_json(row["payload_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_experiment",
    "get_experiment",
    "list_experiments",
    "update_experiment",
    "add_variant",
    "get_variant",
    "list_variants",
    "list_due_experiments",
]
