from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


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


def list_runnable_agent_runs(
    *,
    client_id: str,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    rows = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_runs
            WHERE client_id = ?
              AND run_mode = 'auto_execute_safe'
              AND status IN ('planned', 'running')
              AND (
                  lock_token IS NULL
                  OR lock_expires_at IS NULL
                  OR lock_expires_at <= datetime('now')
              )
            ORDER BY
              CASE status WHEN 'running' THEN 0 ELSE 1 END,
              updated_at ASC
            LIMIT ?
            """,
            (client_id, limit),
        )
        .fetchall()
    )
    return [_row(r) for r in rows]


def acquire_run_lock(*, run_id: str, lock_token: str, ttl_seconds: int = 30) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE agent_runs
        SET
            lock_token = ?,
            lock_acquired_at = datetime('now'),
            lock_expires_at = datetime('now', ?),
            updated_at = datetime('now')
        WHERE id = ?
          AND (
              lock_token IS NULL
              OR lock_expires_at IS NULL
              OR lock_expires_at <= datetime('now')
              OR lock_token = ?
          )
        """,
        (lock_token, f"+{max(1, int(ttl_seconds))} seconds", run_id, lock_token),
    )
    conn.commit()
    return bool(cursor.rowcount and cursor.rowcount > 0)


def heartbeat_run_lock(*, run_id: str, lock_token: str, ttl_seconds: int = 30) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE agent_runs
        SET
            last_heartbeat_at = datetime('now'),
            lock_expires_at = datetime('now', ?),
            updated_at = datetime('now')
        WHERE id = ? AND lock_token = ?
        """,
        (f"+{max(1, int(ttl_seconds))} seconds", run_id, lock_token),
    )
    conn.commit()
    return bool(cursor.rowcount and cursor.rowcount > 0)


def release_run_lock(*, run_id: str, lock_token: str) -> bool:
    conn = get_connection()
    cursor = conn.execute(
        """
        UPDATE agent_runs
        SET
            lock_token = NULL,
            lock_acquired_at = NULL,
            lock_expires_at = NULL,
            updated_at = datetime('now')
        WHERE id = ? AND lock_token = ?
        """,
        (run_id, lock_token),
    )
    conn.commit()
    return bool(cursor.rowcount and cursor.rowcount > 0)


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
        "lock_token": row["lock_token"] if "lock_token" in row.keys() else None,
        "lock_acquired_at": row["lock_acquired_at"]
        if "lock_acquired_at" in row.keys()
        else None,
        "lock_expires_at": row["lock_expires_at"]
        if "lock_expires_at" in row.keys()
        else None,
    }


__all__ = [
    "create_agent_run",
    "update_agent_run",
    "get_agent_run",
    "list_agent_runs",
    "list_runnable_agent_runs",
    "acquire_run_lock",
    "heartbeat_run_lock",
    "release_run_lock",
]
