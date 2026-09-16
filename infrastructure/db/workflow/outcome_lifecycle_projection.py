"""Atomic compatibility projection writes for durable completion decisions."""

from __future__ import annotations

import sqlite3
from typing import Any

from domain.workflow.outcome_lifecycle import CompletionProjectionFence
from domain.workflow.outcomes import CompletionDecision
from infrastructure.db.workflow.outcome_rows import canonical_json


def persist_completion_projection_locked(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    decision: CompletionDecision,
    decision_digest: str,
    completion_fence: CompletionProjectionFence,
    payload: dict[str, Any],
    projected_run_status: str,
    projected_run_state: str,
) -> bool:
    """Write lifecycle history, projection, audit event, and terminal status."""

    blockers = payload["blockers"]
    event_id = f"completion-lifecycle:{decision.decision_id}"
    created_at = payload["evaluated_at"]
    event_payload = {
        "decision_id": decision.decision_id,
        "decision_digest": decision_digest,
        "graph_revision": decision.graph_revision,
        "completion_status": decision.status.value,
        "prior_run_status": completion_fence.run_status,
        "projected_run_status": projected_run_status,
        "prior_run_state": completion_fence.run_state,
        "projected_run_state": projected_run_state,
        "action_projection_digest": completion_fence.action_projection_digest,
        "blockers": blockers,
    }
    conn.execute(
        """
        INSERT INTO workflow_completion_lifecycle_events (
            event_id, tenant_id, workflow_id, graph_revision, decision_id,
            decision_digest, completion_status, prior_run_status,
            projected_run_status, prior_run_state, projected_run_state,
            action_projection_digest,
            authoritative_event_sequence, payload_json, command_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event_id,
            decision.tenant_id,
            decision.workflow_id,
            decision.graph_revision,
            decision.decision_id,
            decision_digest,
            decision.status.value,
            completion_fence.run_status,
            projected_run_status,
            completion_fence.run_state,
            projected_run_state,
            completion_fence.action_projection_digest,
            decision.authoritative_event_sequence,
            canonical_json(event_payload),
            command["command_id"],
            created_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO workflow_completion_projections (
            tenant_id, workflow_id, graph_revision, decision_id,
            decision_digest, criteria_digest, completion_status,
            projected_run_status, projected_run_state,
            authoritative_event_sequence, action_projection_digest,
            blockers_json, evaluated_at, projection_version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
        ON CONFLICT (tenant_id, workflow_id) DO UPDATE SET
            graph_revision = excluded.graph_revision,
            decision_id = excluded.decision_id,
            decision_digest = excluded.decision_digest,
            criteria_digest = excluded.criteria_digest,
            completion_status = excluded.completion_status,
            projected_run_status = excluded.projected_run_status,
            projected_run_state = excluded.projected_run_state,
            authoritative_event_sequence = excluded.authoritative_event_sequence,
            action_projection_digest = excluded.action_projection_digest,
            blockers_json = excluded.blockers_json,
            evaluated_at = excluded.evaluated_at,
            projection_version = workflow_completion_projections.projection_version + 1,
            updated_at = excluded.updated_at
        """,
        (
            decision.tenant_id,
            decision.workflow_id,
            decision.graph_revision,
            decision.decision_id,
            decision_digest,
            decision.criteria_hash,
            decision.status.value,
            projected_run_status,
            projected_run_state,
            decision.authoritative_event_sequence,
            completion_fence.action_projection_digest,
            canonical_json(blockers),
            created_at,
            created_at,
        ),
    )
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, action_id, sequence, event_type, status,
            note_text, is_policy_event, anchors_json, created_at
        ) VALUES (?, ?, NULL, ?, 'completion_decision_recorded', ?, ?, 1, ?, ?)
        """,
        (
            event_id,
            decision.workflow_id,
            decision.authoritative_event_sequence,
            projected_run_status,
            f"Durable completion decision: {decision.status.value}",
            canonical_json(event_payload),
            created_at,
        ),
    )
    cursor = conn.execute(
        """
        UPDATE agent_runs
        SET status = ?, state = ?, error_text = NULL, updated_at = ?
        WHERE id = ? AND client_id = ?
          AND status = ? AND state = ? AND active_graph_revision = ?
        """,
        (
            projected_run_status,
            projected_run_state,
            created_at,
            decision.workflow_id,
            decision.tenant_id,
            completion_fence.run_status,
            completion_fence.run_state,
            completion_fence.active_graph_revision,
        ),
    )
    return cursor.rowcount == 1


__all__ = ["persist_completion_projection_locked"]
