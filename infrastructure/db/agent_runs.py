from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_agent_run(
    *,
    client_id: str,
    brand_id: Optional[str],
    product_id: Optional[str],
    experiment_id: Optional[str],
    objective: Dict[str, Any],
    allowed_capabilities: List[str],
    capability_versions: Dict[str, Any],
    budgets: Dict[str, Any],
    approval_policy: Dict[str, Any],
    requires_approval: bool,
    run_mode: str,
    state: str,
    status: str,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_runs (
            id,
            client_id,
            brand_id,
            product_id,
            experiment_id,
            objective_json,
            allowed_capabilities_json,
            capability_versions_json,
            budgets_json,
            approval_policy_json,
            requires_approval,
            run_mode,
            state,
            status
        )
        VALUES (?, ?, ?, ?, ?, json(?), json(?), json(?), json(?), json(?), ?, ?, ?, ?)
        """,
        (
            run_id,
            client_id,
            brand_id,
            product_id,
            experiment_id,
            to_json(objective) or to_json({}),
            to_json(allowed_capabilities) or to_json([]),
            to_json(capability_versions) or to_json({}),
            to_json(budgets) or to_json({}),
            to_json(approval_policy) or to_json({}),
            1 if requires_approval else 0,
            run_mode,
            state,
            status,
        ),
    )
    conn.commit()
    return get_agent_run(run_id) or {}


def update_agent_run(
    *,
    run_id: str,
    status: Optional[str] = None,
    state: Optional[str] = None,
    run_mode: Optional[str] = None,
    error: Optional[str] = None,
    last_heartbeat_at: Optional[str] = None,
) -> Dict[str, Any] | None:
    conn = get_connection()
    updates: list[str] = []
    params: list[Any] = []
    if status is not None:
        updates.append("status = ?")
        params.append(status)
    if state is not None:
        updates.append("state = ?")
        params.append(state)
    if run_mode is not None:
        updates.append("run_mode = ?")
        params.append(run_mode)
    if error is not None:
        updates.append("error_text = ?")
        params.append(error)
    if last_heartbeat_at is not None:
        updates.append("last_heartbeat_at = ?")
        params.append(last_heartbeat_at)
    updates.append("updated_at = datetime('now')")
    params.append(run_id)
    conn.execute(
        f"""
        UPDATE agent_runs
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        params,
    )
    conn.commit()
    return get_agent_run(run_id)


def get_agent_run(run_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM agent_runs WHERE id = ?", (run_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_agent_runs(
    *,
    client_id: str,
    experiment_id: Optional[str] = None,
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    filters: list[str] = ["client_id = ?"]
    params: list[Any] = [client_id]
    if experiment_id:
        filters.append("experiment_id = ?")
        params.append(experiment_id)
    if product_id:
        filters.append("product_id = ?")
        params.append(product_id)
    if status:
        filters.append("status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(filters)}"
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT * FROM agent_runs
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        .fetchall()
    )
    return [_row(r) for r in rows]


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "experiment_id": row["experiment_id"],
        "objective": from_json(row["objective_json"], default={}),
        "allowed_capabilities": from_json(row["allowed_capabilities_json"], default=[]),
        "capability_versions": from_json(row["capability_versions_json"], default={}),
        "budgets": from_json(row["budgets_json"], default={}),
        "approval_policy": from_json(row["approval_policy_json"], default={}),
        "requires_approval": bool(row["requires_approval"])
        if row["requires_approval"] is not None
        else True,
        "run_mode": row["run_mode"] if "run_mode" in row.keys() else "plan_only",
        "state": row["state"],
        "status": row["status"],
        "error": row["error_text"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "last_heartbeat_at": row["last_heartbeat_at"],
    }


__all__ = [
    "create_agent_run",
    "update_agent_run",
    "get_agent_run",
    "list_agent_runs",
]
