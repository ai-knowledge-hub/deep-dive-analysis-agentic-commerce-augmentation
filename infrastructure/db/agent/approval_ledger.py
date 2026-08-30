from __future__ import annotations

import sqlite3
import uuid
from typing import Any, Dict, List, Optional

from domain.workflow.approval import (
    ApprovalBinding,
    ApprovalContractError,
    ApprovalEnvelope,
    ApprovalStatus,
    can_transition_approval,
)
from domain.workflow.approval_serialization import (
    approval_envelope_digest,
    approval_envelope_from_payload,
)
from domain.workflow.approval_execution import approval_execution_source_digest
import infrastructure.db.agent.approval_persistence as approval_persistence
from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


_SUPERSESSION_SCOPE_FIELDS = (
    "tenant_id",
    "principal_type",
    "principal_id",
    "workflow_id",
    "capability_id",
    "tool_id",
    "effect_class",
    "native_target",
    "authority_hash",
    "registry_version",
    "registry_fingerprint",
    "harness_id",
    "harness_version",
    "policy_profile_id",
    "policy_version",
)
_ALLOWED_ACTION_PROJECTION_TRANSITIONS = frozenset(
    {
        ("proposed", None),
        ("proposed", "approved"),
        ("proposed", "rejected"),
        ("approved", "approved"),
        ("approved", "rejected"),
        ("executing", "rejected"),
    }
)


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
    return approval_persistence.approval_row(row) if row else None


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
    return approval_persistence.approval_row(row) if row else None


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
    return [approval_persistence.approval_row(row) for row in rows]


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
    return [approval_persistence.event_row(row) for row in rows]


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
    return approval_persistence.command_row(row) if row else None


def get_effect_execution(
    *, tenant_id: str, workflow_id: str, effect_idempotency_key: str
) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM approval_effect_executions
            WHERE tenant_id = ? AND workflow_id = ? AND effect_idempotency_key = ?
            """,
            (tenant_id, workflow_id, effect_idempotency_key),
        )
        .fetchone()
    )
    return approval_persistence.effect_execution_row(row) if row else None


def commit_effect_authorization(
    *,
    execution_id: str,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    approval_id: str,
    envelope_digest: str,
    authorization_source_digest: str,
    effect_idempotency_key: str,
    authorized_at: str,
    audit_event: Dict[str, Any],
) -> Dict[str, Any]:
    """Linearize one exact, single-use approval immediately before its effect."""

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        envelope, error = _validated_history_envelope_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            approval_id=approval_id,
        )
        if error or envelope is None:
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": (error or {}).get("reason", "approval does not exist"),
            }
        if (
            envelope.status is not ApprovalStatus.APPROVED
            or approval_envelope_digest(envelope) != envelope_digest
            or envelope.binding.action_id != action_id
            or envelope.binding.effect_idempotency_key != effect_idempotency_key
        ):
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": "approval is no longer valid for this exact effect",
            }
        now = approval_persistence.parse_timestamp(authorized_at)
        if now >= envelope.binding.expires_at:
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": "approval expired before the effect authorization commit",
            }
        scope = approval_persistence.runtime_scope_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            action_id=action_id,
        )
        if scope is None:
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": "governed action no longer exists in workflow scope",
            }
        run, action = scope
        if (
            action.get("status") != "executing"
            or action.get("approval_id") != approval_id
            or action.get("approval_envelope_digest") != envelope_digest
            or approval_execution_source_digest(run=run, action=action)
            != authorization_source_digest
        ):
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": "runtime source changed after approval revalidation",
            }

        existing = conn.execute(
            """
            SELECT * FROM approval_effect_executions
            WHERE approval_id = ?
               OR (tenant_id = ? AND workflow_id = ? AND effect_idempotency_key = ?)
            LIMIT 1
            """,
            (approval_id, tenant_id, workflow_id, effect_idempotency_key),
        ).fetchone()
        if existing:
            current = approval_persistence.effect_execution_row(existing)
            same_identity = all(
                current[field] == expected
                for field, expected in {
                    "tenant_id": tenant_id,
                    "workflow_id": workflow_id,
                    "action_id": action_id,
                    "approval_id": approval_id,
                    "approval_envelope_digest": envelope_digest,
                    "authorization_source_digest": authorization_source_digest,
                    "effect_idempotency_key": effect_idempotency_key,
                }.items()
            )
            conn.rollback()
            if same_identity:
                return {
                    "outcome": "completed"
                    if current["status"] == "succeeded"
                    else "reconcile",
                    "execution": current,
                }
            return {
                "outcome": "identity_conflict",
                "reason": "approval or effect identity was already consumed differently",
            }

        conn.execute(
            """
            INSERT INTO approval_effect_executions (
                execution_id, tenant_id, workflow_id, action_id, approval_id,
                approval_envelope_digest, authorization_source_digest,
                effect_idempotency_key, status, started_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'started', ?, ?)
            """,
            (
                execution_id,
                tenant_id,
                workflow_id,
                action_id,
                approval_id,
                envelope_digest,
                authorization_source_digest,
                effect_idempotency_key,
                authorized_at,
                authorized_at,
            ),
        )
        approval_persistence.insert_agent_audit_event_locked(
            conn,
            workflow_id=workflow_id,
            action_id=action_id,
            event=audit_event,
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return {"outcome": "identity_conflict", "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise
    return {
        "outcome": "started",
        "execution": get_effect_execution(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            effect_idempotency_key=effect_idempotency_key,
        ),
    }


def mark_effect_execution_uncertain(
    *,
    execution_id: str,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    error_code: str,
    occurred_at: str,
    audit_event: Dict[str, Any],
) -> Dict[str, Any]:
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        cursor = conn.execute(
            """
            UPDATE approval_effect_executions
            SET status = 'uncertain', error_code = ?, updated_at = ?
            WHERE execution_id = ? AND tenant_id = ? AND workflow_id = ?
              AND action_id = ? AND status = 'started'
            """,
            (
                error_code,
                occurred_at,
                execution_id,
                tenant_id,
                workflow_id,
                action_id,
            ),
        )
        row = conn.execute(
            """
            SELECT * FROM approval_effect_executions
            WHERE execution_id = ? AND tenant_id = ? AND workflow_id = ?
            """,
            (execution_id, tenant_id, workflow_id),
        ).fetchone()
        if not row:
            conn.rollback()
            return {"outcome": "not_found"}
        current = approval_persistence.effect_execution_row(row)
        if cursor.rowcount == 1:
            approval_persistence.insert_agent_audit_event_locked(
                conn,
                workflow_id=workflow_id,
                action_id=action_id,
                event=audit_event,
            )
            conn.commit()
            return {"outcome": "uncertain", "execution": current}
        conn.rollback()
        return {
            "outcome": "completed" if current["status"] == "succeeded" else "uncertain",
            "execution": current,
        }
    except Exception:
        conn.rollback()
        raise


def commit_effect_completion(
    *,
    execution_id: str,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    approval_id: str,
    expected_envelope_digest: str,
    effect_idempotency_key: str,
    receipt_id: str,
    outputs: Dict[str, Any],
    outputs_hash: str,
    completed_at: str,
    command_id: str,
    idempotency_key: str,
    request_hash: str,
    result: Dict[str, Any],
    mutation: Dict[str, Any],
    audit_events: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Atomically persist receipt, fulfillment, action outcome, and audit links."""

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT * FROM approval_effect_executions
            WHERE execution_id = ? AND tenant_id = ? AND workflow_id = ?
            """,
            (execution_id, tenant_id, workflow_id),
        ).fetchone()
        if not row:
            conn.rollback()
            return {"outcome": "not_found"}
        execution = approval_persistence.effect_execution_row(row)
        exact_identity = all(
            execution[field] == expected
            for field, expected in {
                "action_id": action_id,
                "approval_id": approval_id,
                "approval_envelope_digest": expected_envelope_digest,
                "effect_idempotency_key": effect_idempotency_key,
            }.items()
        )
        if not exact_identity:
            conn.rollback()
            return {
                "outcome": "identity_conflict",
                "reason": "effect completion does not match the authorized identity",
            }
        if execution["status"] == "succeeded":
            conn.rollback()
            if (
                execution["receipt_id"] == receipt_id
                and execution["outputs_hash"] == outputs_hash
            ):
                return {"outcome": "replayed", "execution": execution}
            return {
                "outcome": "identity_conflict",
                "reason": "completed effect was reconciled with different evidence",
            }
        if execution["status"] not in {"started", "uncertain"}:
            conn.rollback()
            return {"outcome": "state_conflict"}

        envelope, error = _validated_history_envelope_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            approval_id=approval_id,
        )
        if error or envelope is None:
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": (error or {}).get("reason", "approval does not exist"),
            }
        if (
            envelope.status is not ApprovalStatus.APPROVED
            or approval_envelope_digest(envelope) != expected_envelope_digest
        ):
            conn.rollback()
            return {
                "outcome": "authorization_conflict",
                "reason": "approval changed after the effect was authorized",
            }
        try:
            fulfilled = approval_envelope_from_payload(dict(mutation["envelope"]))
        except (ApprovalContractError, KeyError, TypeError):
            conn.rollback()
            return {
                "outcome": "validation_error",
                "reason": "effect fulfillment is not a canonical approval envelope",
            }
        if (
            fulfilled.status is not ApprovalStatus.FULFILLED
            or fulfilled.binding != envelope.binding
            or fulfilled.fulfillment_receipt_id != receipt_id
            or approval_envelope_digest(fulfilled) != mutation.get("envelope_digest")
            or not can_transition_approval(envelope.status, fulfilled.status)
        ):
            conn.rollback()
            return {
                "outcome": "validation_error",
                "reason": "effect fulfillment changed the approved binding or receipt",
            }
        action_row = conn.execute(
            """
            SELECT status FROM agent_actions
            WHERE id = ? AND agent_run_id = ?
            """,
            (action_id, workflow_id),
        ).fetchone()
        if not action_row or str(action_row["status"]) not in {"executing", "failed"}:
            conn.rollback()
            return {
                "outcome": "action_state_conflict",
                "reason": "action is not awaiting effect completion or reconciliation",
            }

        result_json = to_json(result) or to_json({})
        result_hash = str(result["result_hash"])
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
            VALUES (?, ?, ?, ?, ?, 'fulfill', '1.0', 'internal_agent',
                    'agent-runtime', 'pre-effect-authorization', '1.0', ?, ?, ?,
                    'committed', json(?), ?, ?, ?, ?, ?)
            """,
            (
                command_id,
                tenant_id,
                workflow_id,
                action_id,
                approval_id,
                idempotency_key,
                request_hash,
                int(mutation["expected_sequence"]),
                result_json,
                result_hash,
                int(mutation["sequence"]),
                int(mutation["sequence"]),
                completed_at,
                completed_at,
            ),
        )
        conflict = _apply_mutation(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            action_id=action_id,
            mutation=mutation,
        )
        if conflict:
            conn.rollback()
            return {"outcome": "authorization_conflict", "reason": conflict}
        conn.execute(
            """
            INSERT INTO approval_events (
                event_id, tenant_id, workflow_id, action_id, approval_id,
                sequence, event_type, event_version, status, envelope_json,
                envelope_digest, command_id, event_index, principal_type,
                principal_id, authority_source, authority_version, occurred_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'approval_fulfilled', '1.0', 'fulfilled',
                    json(?), ?, ?, 0, 'internal_agent', 'agent-runtime',
                    'pre-effect-authorization', '1.0', ?)
            """,
            (
                str(uuid.uuid4()),
                tenant_id,
                workflow_id,
                action_id,
                approval_id,
                int(mutation["sequence"]),
                to_json(mutation["envelope"]) or to_json({}),
                mutation["envelope_digest"],
                command_id,
                completed_at,
            ),
        )
        conn.execute(
            """
            UPDATE approval_effect_executions
            SET status = 'succeeded', receipt_id = ?, outputs_hash = ?,
                error_code = NULL, completed_at = ?, updated_at = ?
            WHERE execution_id = ? AND status IN ('started', 'uncertain')
            """,
            (receipt_id, outputs_hash, completed_at, completed_at, execution_id),
        )
        conn.execute(
            """
            UPDATE agent_actions
            SET status = 'executed', outputs_json = json(?), outputs_hash = ?,
                receipt_id = ?, error_text = NULL,
                approval_id = ?, approval_envelope_digest = ?,
                updated_at = datetime('now')
            WHERE id = ? AND agent_run_id = ? AND status IN ('executing', 'failed')
            """,
            (
                to_json(outputs) or to_json({}),
                outputs_hash,
                receipt_id,
                approval_id,
                mutation["envelope_digest"],
                action_id,
                workflow_id,
            ),
        )
        for event in audit_events:
            approval_persistence.insert_agent_audit_event_locked(
                conn,
                workflow_id=workflow_id,
                action_id=action_id,
                event=event,
            )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        return {"outcome": "identity_conflict", "reason": str(exc)}
    except Exception:
        conn.rollback()
        raise
    return {
        "outcome": "committed",
        "execution": get_effect_execution(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            effect_idempotency_key=effect_idempotency_key,
        ),
    }


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
    expected_action_status: str,
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
            existing = approval_persistence.command_row(replay)
            if existing["request_hash"] != request_hash:
                return {"outcome": "idempotency_conflict", "command": existing}
            return {"outcome": "replayed", "command": existing}

        if (
            type(expected_action_status) is not str
            or (action_status is not None and type(action_status) is not str)
            or (expected_action_status, action_status)
            not in (_ALLOWED_ACTION_PROJECTION_TRANSITIONS)
        ):
            conn.rollback()
            return {
                "outcome": "action_state_conflict",
                "reason": "approval command requested an invalid action lifecycle transition",
            }

        action_row = conn.execute(
            """
            SELECT a.status
            FROM agent_actions a
            JOIN agent_runs r ON r.id = a.agent_run_id
            WHERE a.id = ? AND a.agent_run_id = ? AND r.client_id = ?
            """,
            (action_id, workflow_id, tenant_id),
        ).fetchone()
        if not action_row or str(action_row["status"] or "") != expected_action_status:
            conn.rollback()
            return {
                "outcome": "action_state_conflict",
                "reason": "governed action lifecycle state changed before approval commit",
            }

        if command_type in {"reject", "revoke", "expire", "supersede"}:
            started_effect = conn.execute(
                """
                SELECT status FROM approval_effect_executions
                WHERE tenant_id = ? AND workflow_id = ? AND approval_id = ?
                LIMIT 1
                """,
                (tenant_id, workflow_id, approval_id),
            ).fetchone()
            if started_effect:
                conn.rollback()
                return {
                    "outcome": "validation_error",
                    "code": "effect_already_started",
                    "status_code": 409,
                    "reason": (
                        "approval can no longer be revoked, expired, rejected, or "
                        "superseded after its exact effect was committed for execution"
                    ),
                }

        supersession_error = _validate_supersession_mutations_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            action_id=action_id,
            command_type=command_type,
            mutations=mutations,
        )
        if supersession_error:
            conn.rollback()
            return {"outcome": "validation_error", **supersession_error}

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
                SET status = ?, approval_id = ?, approval_envelope_digest = ?,
                    updated_at = datetime('now')
                WHERE id = ? AND agent_run_id = ? AND status = ?
                """,
                (
                    action_status,
                    approval_id,
                    str(mutations[-1]["envelope_digest"]),
                    action_id,
                    workflow_id,
                    expected_action_status,
                ),
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


def _validate_supersession_mutations_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    command_type: str,
    mutations: List[Dict[str, Any]],
) -> Dict[str, Any] | None:
    superseded = [item for item in mutations if item.get("status") == "superseded"]
    if not superseded:
        return None
    if len(superseded) != 1:
        return _validation_error(
            "invalid_supersession_command",
            "approval command must append exactly one supersession edge",
        )
    mutation = superseded[0]
    if command_type != "supersede":
        return _validation_error(
            "invalid_supersession_command",
            "supersession edge requires a supersede command receipt",
        )
    try:
        proposed = approval_envelope_from_payload(dict(mutation["envelope"]))
    except (ApprovalContractError, KeyError, TypeError):
        return _validation_error(
            "invalid_supersession_command",
            "supersession mutation is not a canonical approval envelope",
        )
    if (
        proposed.status is not ApprovalStatus.SUPERSEDED
        or approval_envelope_digest(proposed) != mutation.get("envelope_digest")
        or proposed.binding.approval_id != mutation.get("approval_id")
        or proposed.binding.action_id != action_id
    ):
        return _validation_error(
            "invalid_supersession_command",
            "supersession mutation does not match its governed approval",
        )
    source, error = _validated_history_envelope_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        approval_id=proposed.binding.approval_id,
    )
    if error:
        return error
    if (
        source is None
        or source.binding != proposed.binding
        or not can_transition_approval(source.status, proposed.status)
    ):
        return _validation_error(
            "invalid_supersession_command",
            "supersession mutation changed the source approval binding",
        )
    replacement_id = str(proposed.supersession_reference or "")
    current_id = replacement_id
    visited: set[str] = set()
    while current_id:
        if current_id == source.binding.approval_id or current_id in visited:
            return _validation_error(
                "supersession_cycle",
                "replacement approval would create a supersession cycle",
            )
        visited.add(current_id)
        current, error = _validated_history_envelope_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            approval_id=current_id,
        )
        if error:
            return error
        if current is None:
            return _validation_error(
                "replacement_approval_not_found",
                "replacement approval does not exist in the same tenant and workflow",
                status_code=404,
            )
        if not _bindings_have_compatible_supersession_scope(
            source.binding, current.binding
        ):
            return _validation_error(
                "replacement_scope_mismatch",
                "replacement approval has incompatible authority or effect scope",
            )
        if current.status is not ApprovalStatus.SUPERSEDED:
            return None
        current_id = str(current.supersession_reference or "")
    return _validation_error(
        "corrupt_approval_history",
        "superseded approval history has no replacement reference",
        status_code=500,
    )


def _validated_history_envelope_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    approval_id: str,
) -> tuple[ApprovalEnvelope | None, Dict[str, Any] | None]:
    record = conn.execute(
        """
        SELECT *
        FROM approval_records
        WHERE approval_id = ? AND tenant_id = ? AND workflow_id = ?
        """,
        (approval_id, tenant_id, workflow_id),
    ).fetchone()
    if not record:
        return None, None
    tail = conn.execute(
        """
        SELECT *
        FROM approval_events
        WHERE approval_id = ? AND tenant_id = ? AND workflow_id = ?
        ORDER BY sequence DESC
        LIMIT 1
        """,
        (approval_id, tenant_id, workflow_id),
    ).fetchone()
    if not tail:
        return None, _validation_error(
            "corrupt_approval_history",
            "approval projection has no append-only history",
            status_code=500,
        )
    try:
        record_envelope = approval_envelope_from_payload(
            from_json(record["envelope_json"], default={})
        )
        event_envelope = approval_envelope_from_payload(
            from_json(tail["envelope_json"], default={})
        )
    except (ApprovalContractError, TypeError):
        return None, _validation_error(
            "corrupt_approval_history",
            "approval projection or event is not canonical",
            status_code=500,
        )
    if (
        approval_envelope_digest(record_envelope) != record["envelope_digest"]
        or approval_envelope_digest(event_envelope) != tail["envelope_digest"]
        or str(record["approval_id"]) != record_envelope.binding.approval_id
        or str(record["tenant_id"]) != record_envelope.binding.tenant_id
        or str(record["workflow_id"]) != record_envelope.binding.workflow_id
        or str(record["action_id"]) != record_envelope.binding.action_id
        or str(tail["approval_id"]) != event_envelope.binding.approval_id
        or str(tail["tenant_id"]) != event_envelope.binding.tenant_id
        or str(tail["workflow_id"]) != event_envelope.binding.workflow_id
        or str(tail["action_id"]) != event_envelope.binding.action_id
        or str(record["current_status"]) != record_envelope.status.value
        or str(tail["status"]) != event_envelope.status.value
        or int(record["current_sequence"]) != int(tail["sequence"])
        or str(record["current_status"]) != str(tail["status"])
        or str(record["envelope_digest"]) != str(tail["envelope_digest"])
        or str(record["action_id"]) != str(tail["action_id"])
        or record_envelope != event_envelope
    ):
        return None, _validation_error(
            "corrupt_approval_history",
            "approval projection diverges from append-only history",
            status_code=500,
        )
    return record_envelope, None


def _bindings_have_compatible_supersession_scope(
    source: ApprovalBinding, replacement: ApprovalBinding
) -> bool:
    return all(
        getattr(source, field) == getattr(replacement, field)
        for field in _SUPERSESSION_SCOPE_FIELDS
    )


def _validation_error(
    code: str, reason: str, *, status_code: int = 409
) -> Dict[str, Any]:
    return {"code": code, "reason": reason, "status_code": status_code}


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


__all__ = [
    "commit_effect_authorization",
    "commit_effect_completion",
    "commit_approval_command",
    "get_effect_execution",
    "get_approval",
    "get_command_by_idempotency_key",
    "get_current_approval_for_action",
    "list_approval_events",
    "list_approvals_for_action",
    "mark_effect_execution_uncertain",
]
