"""SQLite ledger for governed conversational operator commands."""

from __future__ import annotations

import base64
import binascii
import json
import sqlite3
import uuid
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from domain.workflow.operator_commands import (
    OperatorCommandConflictError,
    OperatorCommandCursorError,
    RECEIPT_CONTRACT,
    canonical_digest,
    proposal_is_expired,
    validate_pause_proposal,
)
from infrastructure.db.core.connection import get_connection


def create_proposal(
    *, proposal: dict[str, Any], current_snapshot_digest: Callable[[], str]
) -> dict[str, Any]:
    validate_pause_proposal(proposal)
    source = proposal["source"]
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        _require_snapshot_digest(proposal, current_snapshot_digest())
        _require_event_head(conn, proposal)
        conn.execute(
            """
            INSERT INTO operator_command_proposals (
                proposal_id, tenant_id, workflow_id, principal_id, command_type,
                proposal_digest, proposal_json, active_graph_revision,
                source_run_status, source_run_state, snapshot_digest,
                snapshot_cursor, latest_event_id, latest_event_timestamp,
                harness_id, policy_profile_id, registry_version,
                registry_fingerprint, preflight_digest, idempotency_key,
                issued_at, expires_at, created_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, json(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                proposal["proposal_id"],
                proposal["tenant_id"],
                proposal["run_id"],
                proposal["principal_id"],
                proposal["command_type"],
                proposal["proposal_digest"],
                _json(proposal),
                source["active_graph_revision"],
                source["run_status"],
                source["run_state"],
                source["snapshot_digest"],
                source["snapshot_cursor"],
                source["latest_event_id"],
                source["latest_event_timestamp"],
                source["harness_id"],
                source["policy_profile_id"],
                source["registry_version"],
                source["registry_fingerprint"],
                proposal["preflight"]["digest"],
                proposal["idempotency_key"],
                proposal["issued_at"],
                proposal["expires_at"],
                proposal["issued_at"],
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise OperatorCommandConflictError(
            "proposal_source_changed",
            "The run changed before the pause proposal could be recorded. Ask again to refresh it.",
        ) from exc
    except Exception:
        conn.rollback()
        raise
    return (
        get_proposal(
            proposal_id=proposal["proposal_id"],
            tenant_id=proposal["tenant_id"],
            workflow_id=proposal["run_id"],
        )
        or {}
    )


def get_proposal(
    *, proposal_id: str, tenant_id: str, workflow_id: str
) -> dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
        SELECT * FROM operator_command_proposals
        WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?
        """,
            (proposal_id, tenant_id, workflow_id),
        )
        .fetchone()
    )
    if row is None:
        return None
    proposal = json.loads(row["proposal_json"])
    validate_pause_proposal(proposal)
    _require_proposal_row_matches(row, proposal)
    return proposal


def get_receipt(
    *, proposal_id: str, tenant_id: str, workflow_id: str
) -> dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
        SELECT *
        FROM operator_command_receipts
        WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?
        """,
            (proposal_id, tenant_id, workflow_id),
        )
        .fetchone()
    )
    if row is None:
        return None
    return {**_verified_receipt(row), "replayed": True}


def list_records(
    *, tenant_id: str, workflow_id: str, limit: int = 50, cursor: str | None = None
) -> dict[str, Any]:
    bounded_limit = max(1, min(int(limit), 100))
    position = _decode_cursor(cursor, tenant_id=tenant_id, workflow_id=workflow_id)
    conn = get_connection()
    try:
        conn.execute("BEGIN")
        total_count = int(
            conn.execute(
                """
                SELECT COUNT(*) AS record_count
                FROM operator_command_proposals
                WHERE tenant_id = ? AND workflow_id = ?
                """,
                (tenant_id, workflow_id),
            ).fetchone()["record_count"]
        )
        proposal_rows = conn.execute(
            """
            SELECT *
            FROM operator_command_proposals
            WHERE tenant_id = ? AND workflow_id = ?
              AND (
                ? IS NULL
                OR created_at < ?
                OR (created_at = ? AND proposal_id < ?)
              )
            ORDER BY created_at DESC, proposal_id DESC
            LIMIT ?
            """,
            (
                tenant_id,
                workflow_id,
                position["created_at"] if position else None,
                position["created_at"] if position else None,
                position["created_at"] if position else None,
                position["proposal_id"] if position else None,
                bounded_limit + 1,
            ),
        ).fetchall()
        visible_rows = proposal_rows[:bounded_limit]
        records = [
            _record_from_row(
                conn,
                row,
                tenant_id=tenant_id,
                workflow_id=workflow_id,
            )
            for row in visible_rows
        ]
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    has_more = len(proposal_rows) > bounded_limit
    next_cursor = None
    if has_more and visible_rows:
        last = visible_rows[-1]
        next_cursor = _encode_cursor(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            created_at=last["created_at"],
            proposal_id=last["proposal_id"],
        )
    return {
        "records": records,
        "page": {
            "limit": bounded_limit,
            "returned_count": len(records),
            "total_count": total_count,
            "has_more": has_more,
            "next_cursor": next_cursor,
        },
    }


def _record_from_row(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    tenant_id: str,
    workflow_id: str,
) -> dict[str, Any]:
    proposal = json.loads(row["proposal_json"])
    validate_pause_proposal(proposal)
    _require_proposal_row_matches(row, proposal)
    receipt_row = conn.execute(
        """
        SELECT * FROM operator_command_receipts
        WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?
        """,
        (proposal["proposal_id"], tenant_id, workflow_id),
    ).fetchone()
    return {
        "proposal": proposal,
        "receipt": _verified_receipt(receipt_row) if receipt_row is not None else None,
    }


def _encode_cursor(
    *, tenant_id: str, workflow_id: str, created_at: str, proposal_id: str
) -> str:
    payload = _json(
        {
            "contract": "operator-command-record-cursor.v1",
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "created_at": created_at,
            "proposal_id": proposal_id,
        }
    ).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(
    cursor: str | None, *, tenant_id: str, workflow_id: str
) -> dict[str, str] | None:
    if cursor is None:
        return None
    if type(cursor) is not str or not cursor or len(cursor) > 4096:
        raise OperatorCommandCursorError("operator command cursor is invalid")
    try:
        padding = "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
    except (binascii.Error, ValueError, UnicodeDecodeError) as exc:
        raise OperatorCommandCursorError("operator command cursor is invalid") from exc
    expected_keys = {
        "contract",
        "tenant_id",
        "workflow_id",
        "created_at",
        "proposal_id",
    }
    if type(payload) is not dict or set(payload) != expected_keys:
        raise OperatorCommandCursorError("operator command cursor is invalid")
    if (
        payload["contract"] != "operator-command-record-cursor.v1"
        or payload["tenant_id"] != tenant_id
        or payload["workflow_id"] != workflow_id
        or type(payload["created_at"]) is not str
        or not payload["created_at"]
        or type(payload["proposal_id"]) is not str
        or not payload["proposal_id"]
    ):
        raise OperatorCommandCursorError(
            "operator command cursor does not match this run"
        )
    return {
        "created_at": payload["created_at"],
        "proposal_id": payload["proposal_id"],
    }


def commit_pause(
    *,
    proposal: dict[str, Any],
    principal_id: str,
    confirmation_state: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    validate_pause_proposal(proposal)
    if proposal["principal_id"] != principal_id:
        raise OperatorCommandConflictError(
            "proposal_principal_mismatch",
            "This pause proposal belongs to a different operator.",
        )
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM operator_command_proposals
            WHERE proposal_id = ? AND tenant_id = ? AND workflow_id = ?
            """,
            (proposal["proposal_id"], proposal["tenant_id"], proposal["run_id"]),
        ).fetchone()
        if row is None:
            raise OperatorCommandConflictError(
                "proposal_not_found", "The pause proposal is not available."
            )
        stored = json.loads(row["proposal_json"])
        validate_pause_proposal(stored)
        _require_proposal_row_matches(row, stored)
        if stored != proposal:
            raise OperatorCommandConflictError(
                "proposal_changed",
                "The pause proposal does not match durable evidence.",
            )

        replay_row = conn.execute(
            """
            SELECT *
            FROM operator_command_receipts
            WHERE proposal_id = ?
            """,
            (proposal["proposal_id"],),
        ).fetchone()
        if replay_row is not None:
            receipt = _verified_receipt(replay_row)
            conn.commit()
            return {**receipt, "replayed": True}

        if proposal_is_expired(proposal):
            raise OperatorCommandConflictError(
                "proposal_expired",
                "The pause proposal expired. Ask again for a fresh proposal.",
            )
        current = confirmation_state()
        if type(current) is not dict:
            raise OperatorCommandConflictError(
                "confirmation_state_unavailable",
                "Current pause evidence could not be verified under the commit lock.",
            )
        _require_snapshot_digest(proposal, current.get("snapshot_digest"))
        current_preflight = current.get("preflight")
        if type(current_preflight) is not dict:
            raise OperatorCommandConflictError(
                "preflight_changed",
                "Pause conditions could not be verified under the commit lock.",
            )
        if canonical_digest(current_preflight) != proposal["preflight"]["digest"]:
            raise OperatorCommandConflictError(
                "preflight_changed",
                "Pause conditions changed after the proposal. Ask again for a fresh proposal.",
            )
        if current_preflight.get("allowed") is not True:
            raise OperatorCommandConflictError(
                "preflight_blocked", "The run can no longer be paused."
            )

        source = proposal["source"]
        run_row = conn.execute(
            "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
            (proposal["run_id"], proposal["tenant_id"]),
        ).fetchone()
        if run_row is None:
            raise OperatorCommandConflictError(
                "run_not_found", "The run is no longer available in this tenant."
            )
        _require_run_fence(run_row, source)
        _require_event_head(conn, proposal)

        updated = conn.execute(
            """
            UPDATE agent_runs
            SET status = 'paused', updated_at = datetime('now')
            WHERE id = ? AND client_id = ?
              AND status = ? AND state = ? AND active_graph_revision = ?
              AND harness_id IS ? AND policy_profile_id IS ?
              AND registry_version IS ? AND registry_fingerprint IS ?
            """,
            (
                proposal["run_id"],
                proposal["tenant_id"],
                source["run_status"],
                source["run_state"],
                source["active_graph_revision"],
                source["harness_id"],
                source["policy_profile_id"],
                source["registry_version"],
                source["registry_fingerprint"],
            ),
        )
        if updated.rowcount != 1:
            raise OperatorCommandConflictError(
                "run_changed", "The run changed before pause confirmation committed."
            )

        receipt_id = str(uuid.uuid4())
        command_event_id = str(uuid.uuid4())
        lifecycle_event_id = str(uuid.uuid4())
        completed_at = datetime.now(timezone.utc).isoformat()
        anchors = {
            "proposal_contract": proposal["contract"],
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "preflight_digest": proposal["preflight"]["digest"],
            "idempotency_key": proposal["idempotency_key"],
            "receipt_id": receipt_id,
            "command_type": "pause",
            "source_snapshot_digest": source["snapshot_digest"],
            "active_graph_revision": source["active_graph_revision"],
            "origin": "operator_conversation",
        }
        _insert_event(
            conn,
            event_id=command_event_id,
            run_row=run_row,
            event_type="operator_command_pause",
            status="completed",
            principal_id=principal_id,
            note="Operator confirmed a conversational pause proposal.",
            anchors=anchors,
        )
        _insert_event(
            conn,
            event_id=lifecycle_event_id,
            run_row=run_row,
            event_type="run_paused",
            status="paused",
            principal_id=principal_id,
            note="Run paused by confirmed operator conversation command.",
            anchors=anchors,
        )
        stopping_event_id: str | None = None
        stopping_conditions = set(
            current_preflight.get("harness", {}).get("stopping_conditions", [])
        )
        if "operator_pause" in stopping_conditions:
            stopping_event_id = str(uuid.uuid4())
            _insert_event(
                conn,
                event_id=stopping_event_id,
                run_row=run_row,
                event_type="run_stopping_condition_met",
                status="paused",
                principal_id=principal_id,
                note="Run paused by operator.",
                anchors={**anchors, "stopping_condition": "operator_pause"},
            )

        request_hash = canonical_digest(
            {"proposal_digest": proposal["proposal_digest"], "confirmed": True}
        )
        receipt_core = {
            "contract": RECEIPT_CONTRACT,
            "receipt_id": receipt_id,
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "tenant_id": proposal["tenant_id"],
            "principal_id": principal_id,
            "run_id": proposal["run_id"],
            "command_type": "pause",
            "idempotency_key": proposal["idempotency_key"],
            "request_hash": request_hash,
            "outcome": "paused",
            "prior_run_status": source["run_status"],
            "resulting_run_status": "paused",
            "resulting_run_state": source["run_state"],
            "active_graph_revision": source["active_graph_revision"],
            "event_ids": {
                "command": command_event_id,
                "lifecycle": lifecycle_event_id,
                "stopping_condition": stopping_event_id,
            },
            "acknowledgement": "control_plane_paused",
            "propagation_state": "runtime_propagation_not_certified",
            "completed_at": completed_at,
        }
        receipt_digest = canonical_digest(receipt_core)
        receipt = {**receipt_core, "receipt_digest": receipt_digest}
        conn.execute(
            """
            INSERT INTO operator_command_receipts (
                receipt_id, proposal_id, tenant_id, workflow_id, principal_id,
                command_type, proposal_digest, idempotency_key, request_hash,
                outcome, prior_run_status, resulting_run_status,
                resulting_run_state, active_graph_revision, command_event_id,
                lifecycle_event_id, stopping_event_id, acknowledgement,
                propagation_state, receipt_json, receipt_digest, completed_at
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?), ?, ?
            )
            """,
            (
                receipt_id,
                proposal["proposal_id"],
                proposal["tenant_id"],
                proposal["run_id"],
                principal_id,
                "pause",
                proposal["proposal_digest"],
                proposal["idempotency_key"],
                request_hash,
                "paused",
                source["run_status"],
                "paused",
                source["run_state"],
                source["active_graph_revision"],
                command_event_id,
                lifecycle_event_id,
                stopping_event_id,
                "control_plane_paused",
                "runtime_propagation_not_certified",
                _json(receipt),
                receipt_digest,
                completed_at,
            ),
        )
        conn.commit()
        return {**receipt, "replayed": False}
    except OperatorCommandConflictError:
        conn.rollback()
        raise
    except Exception:
        conn.rollback()
        raise


def _require_run_fence(row: sqlite3.Row, source: dict[str, Any]) -> None:
    expected = {
        "status": source["run_status"],
        "state": source["run_state"],
        "active_graph_revision": source["active_graph_revision"],
        "harness_id": source["harness_id"],
        "policy_profile_id": source["policy_profile_id"],
        "registry_version": source["registry_version"],
        "registry_fingerprint": source["registry_fingerprint"],
    }
    if any(row[field] != value for field, value in expected.items()):
        raise OperatorCommandConflictError(
            "run_changed",
            "The run lifecycle, revision, or governing pins changed. Ask again for a fresh pause proposal.",
        )
    if row["lock_token"]:
        raise OperatorCommandConflictError(
            "run_busy",
            "The run acquired in-flight work before pause committed. Wait for it to settle and ask again.",
        )


def _require_snapshot_digest(proposal: dict[str, Any], observed: Any) -> None:
    if observed != proposal["source"]["snapshot_digest"]:
        raise OperatorCommandConflictError(
            "snapshot_changed",
            "The run evidence changed after this pause proposal. Ask again for a fresh proposal.",
        )


def _require_event_head(conn: sqlite3.Connection, proposal: dict[str, Any]) -> None:
    row = conn.execute(
        """
        SELECT id, created_at FROM agent_events
        WHERE agent_run_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (proposal["run_id"],),
    ).fetchone()
    source = proposal["source"]
    observed = (row["id"], row["created_at"]) if row is not None else (None, None)
    expected = (source["latest_event_id"], source["latest_event_timestamp"])
    if observed != expected:
        raise OperatorCommandConflictError(
            "event_cursor_changed",
            "The run event history changed. Ask again for a fresh pause proposal.",
        )


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    run_row: sqlite3.Row,
    event_type: str,
    status: str,
    principal_id: str,
    note: str,
    anchors: dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, action_id, sequence, event_type, status,
            capability_name, capability_version, principal_type, principal_id,
            tool_id, skill_id, effect_class, trace_id, note_text,
            is_policy_event, anchors_json
        ) VALUES (?, ?, NULL, 0, ?, ?, NULL, NULL, 'human', ?, NULL, NULL,
                  NULL, ?, ?, 0, json(?))
        """,
        (
            event_id,
            run_row["id"],
            event_type,
            status,
            principal_id,
            run_row["trace_id"],
            note,
            _json(anchors),
        ),
    )


def _require_proposal_row_matches(row: sqlite3.Row, proposal: dict[str, Any]) -> None:
    source = proposal["source"]
    expected = {
        "proposal_id": proposal["proposal_id"],
        "tenant_id": proposal["tenant_id"],
        "workflow_id": proposal["run_id"],
        "principal_id": proposal["principal_id"],
        "command_type": proposal["command_type"],
        "proposal_digest": proposal["proposal_digest"],
        "active_graph_revision": source["active_graph_revision"],
        "source_run_status": source["run_status"],
        "source_run_state": source["run_state"],
        "snapshot_digest": source["snapshot_digest"],
        "snapshot_cursor": source["snapshot_cursor"],
        "latest_event_id": source["latest_event_id"],
        "latest_event_timestamp": source["latest_event_timestamp"],
        "harness_id": source["harness_id"],
        "policy_profile_id": source["policy_profile_id"],
        "registry_version": source["registry_version"],
        "registry_fingerprint": source["registry_fingerprint"],
        "preflight_digest": proposal["preflight"]["digest"],
        "idempotency_key": proposal["idempotency_key"],
        "issued_at": proposal["issued_at"],
        "expires_at": proposal["expires_at"],
    }
    if any(row[field] != value for field, value in expected.items()):
        raise ValueError("operator command proposal column integrity check failed")


def _verified_receipt(row: sqlite3.Row) -> dict[str, Any]:
    receipt = json.loads(row["receipt_json"])
    if type(receipt) is not dict:
        raise ValueError("operator command receipt integrity check failed")
    digest = receipt.pop("receipt_digest", None)
    if digest != row["receipt_digest"] or digest != canonical_digest(receipt):
        raise ValueError("operator command receipt integrity check failed")
    expected = {
        "contract": RECEIPT_CONTRACT,
        "receipt_id": row["receipt_id"],
        "proposal_id": row["proposal_id"],
        "proposal_digest": row["proposal_digest"],
        "tenant_id": row["tenant_id"],
        "principal_id": row["principal_id"],
        "run_id": row["workflow_id"],
        "command_type": row["command_type"],
        "idempotency_key": row["idempotency_key"],
        "request_hash": row["request_hash"],
        "outcome": row["outcome"],
        "prior_run_status": row["prior_run_status"],
        "resulting_run_status": row["resulting_run_status"],
        "resulting_run_state": row["resulting_run_state"],
        "active_graph_revision": int(row["active_graph_revision"]),
        "event_ids": {
            "command": row["command_event_id"],
            "lifecycle": row["lifecycle_event_id"],
            "stopping_condition": row["stopping_event_id"],
        },
        "acknowledgement": row["acknowledgement"],
        "propagation_state": row["propagation_state"],
        "completed_at": row["completed_at"],
    }
    if receipt != expected:
        raise ValueError("operator command receipt column integrity check failed")
    return {**receipt, "receipt_digest": digest}


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


__all__ = [
    "commit_pause",
    "create_proposal",
    "get_proposal",
    "get_receipt",
    "list_records",
]
