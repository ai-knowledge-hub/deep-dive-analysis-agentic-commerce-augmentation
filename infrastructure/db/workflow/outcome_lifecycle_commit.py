"""Fenced transaction logic for workflow completion projections."""

from __future__ import annotations

import sqlite3
from typing import Any

from domain.workflow.lifecycle import (
    WorkflowStatus,
    WorkflowTransitionError,
    require_workflow_transition,
)
from domain.workflow.outcome_lifecycle import CompletionProjectionFence
from domain.workflow.outcomes import CompletionDecision, CompletionStatus
from infrastructure.db.workflow.outcome_lifecycle_projection import (
    persist_completion_projection_locked,
)
from infrastructure.db.workflow.outcome_reads import (
    get_completion_projection_fence_locked,
)


class CompletionLifecycleConflict(RuntimeError):
    """The durable run/action fence changed or cannot transition safely."""


def commit_completion_lifecycle_locked(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    decision: CompletionDecision,
    decision_digest: str,
    completion_fence: CompletionProjectionFence,
    payload: dict[str, Any],
    projected_run_state: str | None,
) -> None:
    if type(completion_fence) is not CompletionProjectionFence:
        raise CompletionLifecycleConflict(
            "completion fence must be exact immutable authority"
        )
    current = get_completion_projection_fence_locked(
        conn,
        tenant_id=decision.tenant_id,
        workflow_id=decision.workflow_id,
    )
    if current is None or current != completion_fence:
        raise CompletionLifecycleConflict(
            "run or action projection changed during evaluation"
        )
    if completion_fence.active_graph_revision != decision.graph_revision:
        raise CompletionLifecycleConflict(
            "completion decision is not for the active graph revision"
        )
    _advance_event_cursor(conn, decision, payload)
    _require_active_governance(conn, command, decision, payload)
    projected_status = _projected_status(conn, decision, completion_fence)
    if (
        type(projected_run_state) is not str
        or not projected_run_state
        or projected_run_state != projected_run_state.strip()
    ):
        raise CompletionLifecycleConflict(
            "projected run state must be a canonical exact string"
        )
    if not persist_completion_projection_locked(
        conn,
        command=command,
        decision=decision,
        decision_digest=decision_digest,
        completion_fence=completion_fence,
        payload=payload,
        projected_run_status=projected_status,
        projected_run_state=projected_run_state,
    ):
        raise CompletionLifecycleConflict(
            "workflow projection changed before completion commit"
        )


def _advance_event_cursor(conn, decision, payload) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO workflow_completion_event_cursors (
            tenant_id, workflow_id, current_sequence, updated_at
        ) VALUES (?, ?, -1, ?)
        """,
        (decision.tenant_id, decision.workflow_id, payload["evaluated_at"]),
    )
    cursor = conn.execute(
        """
        UPDATE workflow_completion_event_cursors
        SET current_sequence = current_sequence + 1, updated_at = ?
        WHERE tenant_id = ? AND workflow_id = ?
          AND current_sequence + 1 = ?
        """,
        (
            payload["evaluated_at"],
            decision.tenant_id,
            decision.workflow_id,
            decision.authoritative_event_sequence,
        ),
    )
    if cursor.rowcount != 1:
        raise CompletionLifecycleConflict(
            "completion event sequence is not the next host cursor"
        )


def _require_active_governance(conn, command, decision, payload) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO workflow_completion_governance (
            tenant_id, workflow_id, graph_revision, criteria_digest,
            activation_command_id, activated_at, governance_version
        ) VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (
            decision.tenant_id,
            decision.workflow_id,
            decision.graph_revision,
            decision.criteria_hash,
            command["command_id"],
            payload["evaluated_at"],
        ),
    )
    governance = conn.execute(
        """
        SELECT graph_revision, criteria_digest
        FROM workflow_completion_governance
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (decision.tenant_id, decision.workflow_id),
    ).fetchone()
    if governance is None or (
        int(governance["graph_revision"]),
        governance["criteria_digest"],
    ) != (decision.graph_revision, decision.criteria_hash):
        raise CompletionLifecycleConflict(
            "completion decision does not use active criteria"
        )


def _projected_status(conn, decision, fence) -> str:
    normalized = fence.run_status.lower()
    if normalized in {"completed", "failed", "canceled", "cancelled"}:
        raise CompletionLifecycleConflict(
            "terminal workflow cannot accept a completion projection"
        )
    outstanding = conn.execute(
        """
        SELECT 1 FROM agent_actions
        WHERE agent_run_id = ?
          AND status NOT IN ('executed', 'rejected') LIMIT 1
        """,
        (decision.workflow_id,),
    ).fetchone()
    any_action = conn.execute(
        "SELECT 1 FROM agent_actions WHERE agent_run_id = ? LIMIT 1",
        (decision.workflow_id,),
    ).fetchone()
    non_rejected = conn.execute(
        """
        SELECT 1 FROM agent_actions
        WHERE agent_run_id = ? AND status <> 'rejected' LIMIT 1
        """,
        (decision.workflow_id,),
    ).fetchone()
    if decision.status is CompletionStatus.COMPLETE:
        if outstanding is not None:
            raise CompletionLifecycleConflict(
                "outstanding actions prevent workflow completion"
            )
        return _transition(normalized, WorkflowStatus.COMPLETED)
    if any_action is not None and non_rejected is None:
        return _transition(normalized, WorkflowStatus.CANCELED)
    return fence.run_status


def _transition(source: str, target: WorkflowStatus) -> str:
    try:
        require_workflow_transition(WorkflowStatus(source), target)
    except (ValueError, WorkflowTransitionError) as exc:
        raise CompletionLifecycleConflict(str(exc)) from exc
    return target.value


__all__ = ["CompletionLifecycleConflict", "commit_completion_lifecycle_locked"]
