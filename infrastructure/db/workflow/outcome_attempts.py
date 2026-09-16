"""Durable host authority for sequential compatibility attempts."""

from __future__ import annotations

import hashlib
import json
import sqlite3

from domain.workflow.outcome_lifecycle import TaskAttemptAuthority
from domain.workflow.outcomes import TaskResult
from infrastructure.db.workflow.outcome_reads import get_task_attempt_authority_locked
from infrastructure.db.workflow.outcome_rows import canonical_json


def validate_attempt_result_locked(
    conn: sqlite3.Connection,
    *,
    result: TaskResult,
    attempt_authority: TaskAttemptAuthority,
) -> None:
    current = get_task_attempt_authority_locked(
        conn,
        tenant_id=result.tenant_id,
        workflow_id=result.workflow_id,
        task_id=result.task_id,
    )
    identity = (
        result.graph_revision,
        result.task_id,
        result.attempt_id,
        result.assignment_id,
        result.producer_principal_id,
    )
    expected = (
        attempt_authority.graph_revision,
        attempt_authority.task_id,
        attempt_authority.attempt_id,
        attempt_authority.assignment_id,
        attempt_authority.producer_principal_id,
    )
    if current != attempt_authority or identity != expected:
        raise ValueError("task result does not match current durable attempt authority")
    row = conn.execute(
        """
        SELECT inputs_json, outputs_json FROM agent_actions
        WHERE id = ? AND agent_run_id = ? AND status = 'executed'
        """,
        (attempt_authority.action_id, result.workflow_id),
    ).fetchone()
    if row is None:
        raise ValueError("durable attempt action is no longer executed")
    payload_hashes = tuple(
        hashlib.sha256(
            canonical_json(json.loads(row[column])).encode("utf-8")
        ).hexdigest()
        for column in ("inputs_json", "outputs_json")
    )
    if (result.task_input_hash, result.payload_hash) != payload_hashes:
        raise ValueError("task result does not match durable action input and output")


def register_sequential_attempt_authority(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    created_at: str,
) -> dict[str, str]:
    """Derive compatibility attempt identity only from durable host state."""

    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            """
            SELECT action.id, action.retry_count, action.inputs_json,
                   run.active_graph_revision, run.principal_id,
                   definition.task_input_hash
            FROM agent_actions action
            JOIN agent_runs run
              ON run.id = action.agent_run_id AND run.client_id = ?
            JOIN workflow_completion_governance governance
              ON governance.tenant_id = run.client_id
             AND governance.workflow_id = run.id
             AND governance.graph_revision = run.active_graph_revision
            JOIN workflow_completion_task_definitions definition
              ON definition.criteria_digest = governance.criteria_digest
             AND definition.task_id = action.id
            WHERE run.id = ? AND action.id = ?
            """,
            (tenant_id, workflow_id, action_id),
        ).fetchone()
        if row is None or not row["principal_id"]:
            raise ValueError(
                "sequential attempt authority lacks a governed action or principal"
            )
        durable_input_hash = hashlib.sha256(
            canonical_json(json.loads(row["inputs_json"])).encode("utf-8")
        ).hexdigest()
        if durable_input_hash != row["task_input_hash"]:
            raise ValueError(
                "sequential attempt authority does not match the task input"
            )
        attempt_id = f"action-attempt:{action_id}:{int(row['retry_count'])}"
        conn.execute(
            """
            INSERT OR IGNORE INTO workflow_completion_attempt_authorities (
                tenant_id, workflow_id, graph_revision, task_id, attempt_id,
                assignment_id, producer_principal_id, action_id, created_at
            ) VALUES (?, ?, ?, ?, ?, NULL, ?, ?, ?)
            """,
            (
                tenant_id,
                workflow_id,
                int(row["active_graph_revision"]),
                action_id,
                attempt_id,
                row["principal_id"],
                action_id,
                created_at,
            ),
        )
        persisted = conn.execute(
            """
            SELECT attempt_id, producer_principal_id, action_id
            FROM workflow_completion_attempt_authorities
            WHERE tenant_id = ? AND workflow_id = ? AND task_id = ?
            """,
            (tenant_id, workflow_id, action_id),
        ).fetchone()
        actual = (
            (
                persisted["attempt_id"],
                persisted["producer_principal_id"],
                persisted["action_id"],
            )
            if persisted is not None
            else None
        )
        if actual != (attempt_id, row["principal_id"], action_id):
            raise ValueError("sequential attempt authority conflicts")
        conn.commit()
        return {
            "task_id": action_id,
            "attempt_id": attempt_id,
            "producer_principal_id": str(row["principal_id"]),
            "action_id": action_id,
        }
    except (ValueError, sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        conn.rollback()
        raise ValueError(str(exc)) from exc


__all__ = ["register_sequential_attempt_authority", "validate_attempt_result_locked"]
