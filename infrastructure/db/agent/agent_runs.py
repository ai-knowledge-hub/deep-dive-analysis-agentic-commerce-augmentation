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
    principal_type: Optional[str] = None,
    principal_id: Optional[str] = None,
    agent_profile_id: Optional[str] = None,
    harness_id: Optional[str] = None,
    policy_profile_id: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    trace_id: Optional[str] = None,
    root_run_id: Optional[str] = None,
    parent_run_id: Optional[str] = None,
    registry_version: Optional[str] = None,
    registry_fingerprint: Optional[str] = None,
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
            status,
            principal_type,
            principal_id,
            agent_profile_id,
            harness_id,
            policy_profile_id,
            idempotency_key,
            trace_id,
            root_run_id,
            parent_run_id,
            registry_version,
            registry_fingerprint
        )
        VALUES (?, ?, ?, ?, ?, json(?), json(?), json(?), json(?), json(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            principal_type,
            principal_id,
            agent_profile_id,
            harness_id,
            policy_profile_id,
            idempotency_key,
            trace_id,
            root_run_id,
            parent_run_id,
            registry_version,
            registry_fingerprint,
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
    policy_profile_id: Optional[str] = None,
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
    if policy_profile_id is not None:
        updates.append("policy_profile_id = ?")
        params.append(policy_profile_id)
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


def restore_agent_run_after_effect_reconciliation(
    *,
    run_id: str,
    client_id: str,
    state: str,
    status: str,
    expected_run_state: str,
    expected_run_status: str,
    expected_action_projection: tuple[tuple[Any, ...], ...],
) -> Dict[str, Any]:
    """CAS a recovery projection against run state and its complete action set."""

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        run_row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (run_id, client_id),
        ).fetchone()
        if run_row is None:
            conn.rollback()
            return {"outcome": "not_found", "run": None}
        current_run = _row(run_row)
        current_status = str(current_run.get("status") or "").strip().lower()
        if current_status in {"canceled", "cancelled", "completed", "paused"}:
            conn.rollback()
            return {"outcome": "control_plane_state_preserved", "run": current_run}
        if (
            current_run.get("state") != expected_run_state
            or current_status != expected_run_status
        ):
            conn.rollback()
            return {"outcome": "run_projection_changed", "run": current_run}
        action_rows = conn.execute(
            """
            SELECT id, sequence, status, capability_name, outputs_hash, error_text
            FROM agent_actions
            WHERE agent_run_id = ?
            ORDER BY sequence ASC, id ASC
            """,
            (run_id,),
        ).fetchall()
        current_action_projection = tuple(
            (
                row["id"],
                int(row["sequence"]),
                row["status"],
                row["capability_name"],
                row["outputs_hash"],
                row["error_text"],
            )
            for row in action_rows
        )
        if current_action_projection != expected_action_projection:
            conn.rollback()
            return {"outcome": "action_projection_changed", "run": current_run}
        conn.execute(
            """
            UPDATE agent_runs
            SET state = ?,
                status = ?,
                error_text = CASE WHEN ? = 'failed' THEN error_text ELSE NULL END,
                updated_at = datetime('now')
            WHERE id = ? AND client_id = ?
            """,
            (state, status, status, run_id, client_id),
        )
        updated_row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (run_id, client_id),
        ).fetchone()
        conn.commit()
        return {"outcome": "restored", "run": _row(updated_row)}
    except Exception:
        conn.rollback()
        raise


def get_agent_run(
    run_id: str, *, client_id: Optional[str] = None
) -> Dict[str, Any] | None:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (run_id, client_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ?", (run_id,)
        ).fetchone()
    return _row(row) if row else None


def delete_agent_run(*, run_id: str, client_id: Optional[str] = None) -> bool:
    conn = get_connection()
    if client_id:
        cursor = conn.execute(
            "DELETE FROM agent_runs WHERE id = ? AND client_id = ?",
            (run_id, client_id),
        )
    else:
        cursor = conn.execute("DELETE FROM agent_runs WHERE id = ?", (run_id,))
    conn.commit()
    return bool(cursor.rowcount and cursor.rowcount > 0)


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


def list_agent_runs_missing_registry_pins(
    *, client_id: str, limit: int = 200
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    rows = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_runs
            WHERE client_id = ?
              AND (
                  registry_version IS NULL
                  OR registry_fingerprint IS NULL
              )
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (client_id, int(limit)),
        )
        .fetchall()
    )
    return [_row(r) for r in rows]


def backfill_agent_run_registry_pins(
    *,
    client_id: str,
    registry_version: str,
    registry_fingerprint: str,
    limit: int = 200,
) -> int:
    run_ids = [
        item["id"]
        for item in list_agent_runs_missing_registry_pins(
            client_id=client_id, limit=limit
        )
    ]
    if not run_ids:
        return 0
    placeholders = ", ".join("?" for _ in run_ids)
    cursor = get_connection().execute(
        f"""
        UPDATE agent_runs
        SET
            registry_version = ?,
            registry_fingerprint = ?,
            updated_at = datetime('now')
        WHERE id IN ({placeholders})
        """,
        (registry_version, registry_fingerprint, *run_ids),
    )
    get_connection().commit()
    return int(cursor.rowcount or 0)


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
        "principal_type": row["principal_type"]
        if "principal_type" in row.keys()
        else None,
        "principal_id": row["principal_id"] if "principal_id" in row.keys() else None,
        "agent_profile_id": row["agent_profile_id"]
        if "agent_profile_id" in row.keys()
        else None,
        "harness_id": row["harness_id"] if "harness_id" in row.keys() else None,
        "policy_profile_id": row["policy_profile_id"]
        if "policy_profile_id" in row.keys()
        else None,
        "idempotency_key": row["idempotency_key"]
        if "idempotency_key" in row.keys()
        else None,
        "trace_id": row["trace_id"] if "trace_id" in row.keys() else None,
        "root_run_id": row["root_run_id"] if "root_run_id" in row.keys() else None,
        "parent_run_id": row["parent_run_id"]
        if "parent_run_id" in row.keys()
        else None,
        "registry_version": row["registry_version"]
        if "registry_version" in row.keys()
        else None,
        "registry_fingerprint": row["registry_fingerprint"]
        if "registry_fingerprint" in row.keys()
        else None,
        "active_graph_revision": int(row["active_graph_revision"])
        if "active_graph_revision" in row.keys()
        else 1,
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
    "delete_agent_run",
    "list_agent_runs",
    "list_agent_runs_missing_registry_pins",
    "backfill_agent_run_registry_pins",
    "list_runnable_agent_runs",
    "acquire_run_lock",
    "heartbeat_run_lock",
    "release_run_lock",
]
