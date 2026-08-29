from __future__ import annotations

import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def get_approval(
    *, approval_id: str, tenant_id: str, workflow_id: str
) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM approval_records
            WHERE approval_id = ? AND tenant_id = ? AND workflow_id = ?
            """,
            (approval_id, tenant_id, workflow_id),
        )
        .fetchone()
    )
    return _approval_row(row) if row else None


def get_current_approval_for_action(
    *, tenant_id: str, workflow_id: str, action_id: str
) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM approval_records
            WHERE tenant_id = ? AND workflow_id = ? AND action_id = ?
            ORDER BY
                CASE current_status
                    WHEN 'approved' THEN 0
                    WHEN 'requested' THEN 1
                    ELSE 2
                END,
                updated_at DESC,
                approval_id DESC
            LIMIT 1
            """,
            (tenant_id, workflow_id, action_id),
        )
        .fetchone()
    )
    return _approval_row(row) if row else None


def list_approvals_for_action(
    *, tenant_id: str, workflow_id: str, action_id: str, limit: int = 100
) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM approval_records
            WHERE tenant_id = ? AND workflow_id = ? AND action_id = ?
            ORDER BY created_at ASC, approval_id ASC
            LIMIT ?
            """,
            (tenant_id, workflow_id, action_id, int(limit)),
        )
        .fetchall()
    )
    return [_approval_row(row) for row in rows]


def list_approval_events(
    *, tenant_id: str, workflow_id: str, approval_id: str, limit: int = 200
) -> List[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM approval_events
            WHERE tenant_id = ? AND workflow_id = ? AND approval_id = ?
            ORDER BY sequence ASC
            LIMIT ?
            """,
            (tenant_id, workflow_id, approval_id, int(limit)),
        )
        .fetchall()
    )
    return [_event_row(row) for row in rows]


def get_command_by_idempotency_key(
    *, tenant_id: str, workflow_id: str, idempotency_key: str
) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM approval_commands
            WHERE tenant_id = ? AND workflow_id = ? AND idempotency_key = ?
            """,
            (tenant_id, workflow_id, idempotency_key),
        )
        .fetchone()
    )
    return _command_row(row) if row else None


def commit_approval_command(
    *,
    command_id: str,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    approval_id: str,
    command_type: str,
    principal_type: str,
    principal_id: str,
    authority_source: str,
    authority_version: str,
    idempotency_key: str,
    request_hash: str,
    received_at: str,
    completed_at: str,
    mutations: List[Dict[str, Any]],
    result: Dict[str, Any],
    action_status: Optional[str],
    audit_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Atomically commit a command receipt, ledger snapshots and projections.

    The adapter reports conflicts as data so the application layer does not
    depend on infrastructure exception types.
    """

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        replay = conn.execute(
            """
            SELECT *
            FROM approval_commands
            WHERE tenant_id = ? AND workflow_id = ? AND idempotency_key = ?
            """,
            (tenant_id, workflow_id, idempotency_key),
        ).fetchone()
        if replay:
            conn.rollback()
            existing = _command_row(replay)
            if existing["request_hash"] != request_hash:
                return {"outcome": "idempotency_conflict", "command": existing}
            return {"outcome": "replayed", "command": existing}

        for mutation in mutations:
            conflict = _apply_mutation(
                conn,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
                action_id=action_id,
                mutation=mutation,
            )
            if conflict:
                conn.rollback()
                return {"outcome": "concurrency_conflict", "reason": conflict}

        if action_status is not None:
            cursor = conn.execute(
                """
                UPDATE agent_actions
                SET status = ?, updated_at = datetime('now')
                WHERE id = ? AND agent_run_id = ?
                """,
                (action_status, action_id, workflow_id),
            )
            if cursor.rowcount != 1:
                conn.rollback()
                return {
                    "outcome": "concurrency_conflict",
                    "reason": "governed action no longer exists in workflow scope",
                }

        first_sequence = min(int(item["sequence"]) for item in mutations)
        last_sequence = max(int(item["sequence"]) for item in mutations)
        result_json = to_json(result) or to_json({})
        result_hash = str(result["result_hash"])
        expected_sequence = mutations[0].get("expected_sequence")
        conn.execute(
            """
            INSERT INTO approval_commands (
                command_id, tenant_id, workflow_id, action_id, approval_id,
                command_type, command_version, principal_type, principal_id,
                authority_source, authority_version, idempotency_key,
                request_hash, expected_sequence, status, result_json,
                result_hash, first_event_sequence, last_event_sequence,
                received_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, '1.0', ?, ?, ?, ?, ?, ?, ?, 'committed',
                    json(?), ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                tenant_id,
                workflow_id,
                action_id,
                approval_id,
                command_type,
                principal_type,
                principal_id,
                authority_source,
                authority_version,
                idempotency_key,
                request_hash,
                expected_sequence,
                result_json,
                result_hash,
                first_sequence,
                last_sequence,
                received_at,
                completed_at,
            ),
        )

        for event_index, mutation in enumerate(mutations):
            conn.execute(
                """
                INSERT INTO approval_events (
                    event_id, tenant_id, workflow_id, action_id, approval_id,
                    sequence, event_type, event_version, status, envelope_json,
                    envelope_digest, command_id, event_index, principal_type,
                    principal_id, authority_source, authority_version, occurred_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, '1.0', ?, json(?), ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(mutation.get("event_id") or uuid.uuid4()),
                    tenant_id,
                    workflow_id,
                    str(mutation.get("action_id") or action_id),
                    mutation["approval_id"],
                    int(mutation["sequence"]),
                    mutation["event_type"],
                    mutation["status"],
                    to_json(mutation["envelope"]) or to_json({}),
                    mutation["envelope_digest"],
                    command_id,
                    event_index,
                    principal_type,
                    principal_id,
                    authority_source,
                    authority_version,
                    mutation["occurred_at"],
                ),
            )

        for audit_event in audit_events:
            conn.execute(
                """
                INSERT INTO agent_events (
                    id, agent_run_id, action_id, sequence, event_type, status,
                    capability_name, capability_version, principal_type,
                    principal_id, tool_id, skill_id, effect_class, trace_id,
                    note_text, is_policy_event, anchors_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, json(?))
                """,
                (
                    str(audit_event.get("id") or uuid.uuid4()),
                    workflow_id,
                    action_id,
                    int(audit_event.get("sequence") or 0),
                    audit_event["event_type"],
                    audit_event["status"],
                    audit_event.get("capability_name"),
                    audit_event.get("capability_version"),
                    principal_type,
                    principal_id,
                    audit_event.get("tool_id"),
                    audit_event.get("skill_id"),
                    audit_event.get("effect_class"),
                    audit_event.get("trace_id"),
                    audit_event.get("note"),
                    to_json(audit_event.get("anchors") or {}) or to_json({}),
                ),
            )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return {"outcome": "concurrency_conflict", "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise

    stored = get_command_by_idempotency_key(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        idempotency_key=idempotency_key,
    )
    return {"outcome": "committed", "command": stored}


def supersession_would_cycle(
    *,
    tenant_id: str,
    workflow_id: str,
    source_approval_id: str,
    replacement_approval_id: str,
) -> bool:
    """Follow durable replacement links and fail closed on any cycle."""

    current = replacement_approval_id
    visited: set[str] = set()
    while current:
        if current == source_approval_id or current in visited:
            return True
        visited.add(current)
        row = get_approval(
            approval_id=current,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
        )
        if not row or row["status"] != "superseded":
            return False
        lifecycle = dict(row["envelope"].get("lifecycle") or {})
        current = str(lifecycle.get("supersession_reference") or "")
    return False


def _apply_mutation(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    mutation: Dict[str, Any],
) -> str | None:
    expected_sequence = mutation.get("expected_sequence")
    mutation_action_id = str(mutation.get("action_id") or action_id)
    envelope_json = to_json(mutation["envelope"]) or to_json({})
    if expected_sequence is None:
        if mutation.get("require_no_existing_action_approval"):
            existing = conn.execute(
                """
                SELECT 1
                FROM approval_records
                WHERE tenant_id = ? AND workflow_id = ? AND action_id = ?
                LIMIT 1
                """,
                (tenant_id, workflow_id, mutation_action_id),
            ).fetchone()
            if existing:
                return "approval lineage was created before command commit"
        try:
            conn.execute(
                """
                INSERT INTO approval_records (
                    approval_id, tenant_id, workflow_id, action_id,
                    current_sequence, current_status, envelope_json,
                    envelope_digest, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, json(?), ?, ?, ?)
                """,
                (
                    mutation["approval_id"],
                    tenant_id,
                    workflow_id,
                    mutation_action_id,
                    int(mutation["sequence"]),
                    mutation["status"],
                    envelope_json,
                    mutation["envelope_digest"],
                    mutation["occurred_at"],
                    mutation["occurred_at"],
                ),
            )
        except sqlite3.IntegrityError as exc:
            return str(exc)
        return None

    cursor = conn.execute(
        """
        UPDATE approval_records
        SET current_sequence = ?, current_status = ?, envelope_json = json(?),
            envelope_digest = ?, updated_at = ?
        WHERE approval_id = ? AND tenant_id = ? AND workflow_id = ?
          AND action_id = ? AND current_sequence = ?
        """,
        (
            int(mutation["sequence"]),
            mutation["status"],
            envelope_json,
            mutation["envelope_digest"],
            mutation["occurred_at"],
            mutation["approval_id"],
            tenant_id,
            workflow_id,
            mutation_action_id,
            int(expected_sequence),
        ),
    )
    if cursor.rowcount != 1:
        return "approval version changed before command commit"
    return None


def _approval_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "approval_id": row["approval_id"],
        "tenant_id": row["tenant_id"],
        "workflow_id": row["workflow_id"],
        "action_id": row["action_id"],
        "sequence": int(row["current_sequence"]),
        "status": row["current_status"],
        "envelope": from_json(row["envelope_json"], default={}),
        "envelope_digest": row["envelope_digest"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _command_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "command_id": row["command_id"],
        "tenant_id": row["tenant_id"],
        "workflow_id": row["workflow_id"],
        "action_id": row["action_id"],
        "approval_id": row["approval_id"],
        "command_type": row["command_type"],
        "command_version": row["command_version"],
        "principal_type": row["principal_type"],
        "principal_id": row["principal_id"],
        "authority_source": row["authority_source"],
        "authority_version": row["authority_version"],
        "idempotency_key": row["idempotency_key"],
        "request_hash": row["request_hash"],
        "expected_sequence": int(row["expected_sequence"])
        if row["expected_sequence"] is not None
        else None,
        "status": row["status"],
        "result": from_json(row["result_json"], default={}),
        "result_hash": row["result_hash"],
        "first_event_sequence": int(row["first_event_sequence"]),
        "last_event_sequence": int(row["last_event_sequence"]),
        "received_at": row["received_at"],
        "completed_at": row["completed_at"],
    }


def _event_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "event_id": row["event_id"],
        "tenant_id": row["tenant_id"],
        "workflow_id": row["workflow_id"],
        "action_id": row["action_id"],
        "approval_id": row["approval_id"],
        "sequence": int(row["sequence"]),
        "event_type": row["event_type"],
        "event_version": row["event_version"],
        "status": row["status"],
        "envelope": from_json(row["envelope_json"], default={}),
        "envelope_digest": row["envelope_digest"],
        "command_id": row["command_id"],
        "event_index": int(row["event_index"]),
        "principal_type": row["principal_type"],
        "principal_id": row["principal_id"],
        "authority_source": row["authority_source"],
        "authority_version": row["authority_version"],
        "occurred_at": row["occurred_at"],
        "recorded_at": row["recorded_at"],
    }


__all__ = [
    "commit_approval_command",
    "get_approval",
    "get_command_by_idempotency_key",
    "get_current_approval_for_action",
    "list_approval_events",
    "list_approvals_for_action",
    "supersession_would_cycle",
]
