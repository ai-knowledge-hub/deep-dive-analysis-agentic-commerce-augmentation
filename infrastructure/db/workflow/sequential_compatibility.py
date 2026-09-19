"""SQLite adapter for the sequential-runtime workflow compatibility shadow."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import sqlite3
from typing import Any

from domain.workflow.sequential_compatibility import (
    SequentialWorkflowCompatibility,
    compile_sequential_workflow,
)
from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json
import infrastructure.db.workflow.outcome_reads as outcome_reads
from infrastructure.db.workflow.semantic_validation import (
    validate_authoritative_semantic_bundles_locked,
)


def project_sequential_run(*, tenant_id: str, run_id: str) -> dict[str, Any]:
    """Compile and append a revision-1 shadow without changing runtime authority."""

    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        run = _load_run_locked(conn, tenant_id=tenant_id, run_id=run_id)
        if run is None:
            raise ValueError("agent run was not found in the tenant scope")
        actions = _load_actions_locked(conn, run_id=run_id)
        events = _load_events_locked(conn, run_id=run_id)
        compiled = compile_sequential_workflow(
            run=run,
            actions=actions,
            events=events,
        )
        existing = conn.execute(
            """
            SELECT structural_digest
            FROM workflow_compatibility_runs
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            (tenant_id, run_id),
        ).fetchone()
        if existing is None:
            _insert_structure_locked(conn, compiled)
            structural_outcome = "created"
        elif existing["structural_digest"] != compiled.structural_digest:
            _upsert_status_locked(
                conn,
                tenant_id=tenant_id,
                workflow_id=run_id,
                projection_state="drifted",
                structural_digest=compiled.structural_digest,
                source_action_count=len(actions),
                projected_task_count=_count_locked(
                    conn,
                    "workflow_compatibility_revision_tasks",
                    tenant_id,
                    run_id,
                ),
                source_event_count=len(events),
                projected_event_count=_count_locked(
                    conn,
                    "workflow_compatibility_events",
                    tenant_id,
                    run_id,
                ),
                error_code="structural_drift",
            )
            conn.commit()
            return {
                "outcome": "drifted",
                "tenant_id": tenant_id,
                "workflow_id": run_id,
                "active_revision": 1,
                "error_code": "structural_drift",
            }
        else:
            structural_outcome = "replayed"

        imported_events = _import_events_locked(conn, compiled)
        validate_authoritative_semantic_bundles_locked(
            conn, tenant_id=tenant_id, workflow_id=run_id
        )
        semantic_sources = _load_semantic_sources_locked(
            conn, tenant_id=tenant_id, workflow_id=run_id
        )
        imported_semantic_artifacts = _import_semantic_artifacts_locked(
            conn, semantic_sources
        )
        projected_task_count = _count_locked(
            conn,
            "workflow_compatibility_revision_tasks",
            tenant_id,
            run_id,
        )
        projected_event_count = _count_locked(
            conn,
            "workflow_compatibility_events",
            tenant_id,
            run_id,
        )
        state = (
            "current"
            if projected_task_count == len(actions)
            and projected_event_count == len(events)
            else "drifted"
        )
        _upsert_status_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=run_id,
            projection_state=state,
            structural_digest=compiled.structural_digest,
            source_action_count=len(actions),
            projected_task_count=projected_task_count,
            source_event_count=len(events),
            projected_event_count=projected_event_count,
            error_code=None if state == "current" else "cardinality_mismatch",
        )
        semantic_state = _semantic_parity_state_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=run_id,
            sources=semantic_sources,
        )
        _upsert_semantic_status_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=run_id,
            parity_state=semantic_state["parity_state"],
            source_artifact_count=len(semantic_sources),
            projected_artifact_count=semantic_state["projected_artifact_count"],
            completion=semantic_state["completion"],
            error_code=semantic_state["error_code"],
        )
        conn.commit()
        return {
            "outcome": state,
            "operation": structural_outcome,
            "tenant_id": tenant_id,
            "workflow_id": run_id,
            "active_revision": 1,
            "imported_events": imported_events,
            "imported_semantic_artifacts": imported_semantic_artifacts,
            "semantic_parity_state": semantic_state["parity_state"],
            "structural_digest": compiled.structural_digest,
        }
    except Exception:
        conn.rollback()
        raise


def get_sequential_projection(*, tenant_id: str, run_id: str) -> dict[str, Any] | None:
    conn = get_connection()
    shadow = conn.execute(
        """
        SELECT * FROM workflow_compatibility_runs
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, run_id),
    ).fetchone()
    if shadow is None:
        return None
    revision = conn.execute(
        """
        SELECT * FROM workflow_compatibility_revisions
        WHERE tenant_id = ? AND workflow_id = ? AND revision = ?
        """,
        (tenant_id, run_id, int(shadow["active_revision"])),
    ).fetchone()
    task_rows = conn.execute(
        """
        SELECT projected.*
        FROM workflow_compatibility_revision_tasks membership
        JOIN workflow_sequential_task_projection projected
          ON projected.tenant_id = membership.tenant_id
         AND projected.workflow_id = membership.workflow_id
         AND projected.task_id = membership.task_id
        WHERE membership.tenant_id = ?
          AND membership.workflow_id = ?
          AND membership.revision = ?
          AND membership.disposition = 'active'
        ORDER BY projected.sequence ASC, projected.task_id ASC
        """,
        (tenant_id, run_id, int(shadow["active_revision"])),
    ).fetchall()
    edge_rows = conn.execute(
        """
        SELECT * FROM workflow_compatibility_edges
        WHERE tenant_id = ? AND workflow_id = ? AND revision = ?
        ORDER BY edge_id ASC
        """,
        (tenant_id, run_id, int(shadow["active_revision"])),
    ).fetchall()
    event_rows = conn.execute(
        """
        SELECT * FROM workflow_compatibility_events
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY sequence ASC
        """,
        (tenant_id, run_id),
    ).fetchall()
    status = conn.execute(
        """
        SELECT * FROM workflow_compatibility_projection_status
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, run_id),
    ).fetchone()
    live_run = conn.execute(
        """
        SELECT * FROM workflow_sequential_run_projection
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, run_id),
    ).fetchone()
    semantic_rows = conn.execute(
        """
        SELECT * FROM workflow_compatibility_semantic_artifacts
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY artifact_type ASC, source_id ASC
        """,
        (tenant_id, run_id),
    ).fetchall()
    semantic_status = conn.execute(
        """
        SELECT * FROM workflow_compatibility_semantic_status
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, run_id),
    ).fetchone()
    structure_and_event_ids_current = _content_is_current(
        conn,
        tenant_id=tenant_id,
        run_id=run_id,
        shadow=shadow,
        revision=revision,
        task_rows=task_rows,
        edge_rows=edge_rows,
        event_rows=event_rows,
        status=status,
        live_run=live_run,
    )
    governed_semantic_parity = _semantic_content_is_current(
        conn,
        tenant_id=tenant_id,
        workflow_id=run_id,
        semantic_rows=semantic_rows,
        semantic_status=semantic_status,
    )
    return {
        "workflow": _dict_row(shadow),
        "revision": _dict_row(revision),
        "run_projection": _dict_row(live_run),
        "tasks": [_dict_row(row) for row in task_rows],
        "edges": [_dict_row(row) for row in edge_rows],
        "events": [_event_row(row) for row in event_rows],
        "semantic_artifacts": [_semantic_row(row) for row in semantic_rows],
        "projection_status": _dict_row(status),
        "semantic_status": _dict_row(semantic_status),
        "structure_and_event_ids_current": structure_and_event_ids_current,
        "governed_semantic_parity": governed_semantic_parity,
    }


def list_projection_candidates(
    *, tenant_id: str, limit: int = 25
) -> list[dict[str, Any]]:
    """Return a bounded, oldest-checked scan for backfill and reconciliation."""

    bounded_limit = max(1, min(int(limit), 100))
    rows = (
        get_connection()
        .execute(
            """
        SELECT run.id AS workflow_id,
               status.projection_state,
               status.checked_at
        FROM agent_runs run
        LEFT JOIN workflow_compatibility_projection_status status
          ON status.tenant_id = run.client_id
         AND status.workflow_id = run.id
        WHERE run.client_id = ?
        ORDER BY
          CASE WHEN status.checked_at IS NULL THEN 0 ELSE 1 END ASC,
          status.checked_at ASC,
          run.created_at ASC,
          run.id ASC
        LIMIT ?
        """,
            (tenant_id, bounded_limit),
        )
        .fetchall()
    )
    return [_dict_row(row) or {} for row in rows]


def record_projection_failure(
    *, tenant_id: str, run_id: str, error_code: str
) -> dict[str, Any]:
    conn = get_connection()
    _upsert_status_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=run_id,
        projection_state="failed",
        structural_digest=None,
        source_action_count=0,
        projected_task_count=0,
        source_event_count=0,
        projected_event_count=0,
        error_code=error_code,
    )
    conn.commit()
    return {
        "outcome": "failed",
        "tenant_id": tenant_id,
        "workflow_id": run_id,
        "error_code": error_code,
    }


def _content_is_current(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    run_id: str,
    shadow: sqlite3.Row,
    revision: sqlite3.Row | None,
    task_rows: list[sqlite3.Row],
    edge_rows: list[sqlite3.Row],
    event_rows: list[sqlite3.Row],
    status: sqlite3.Row | None,
    live_run: sqlite3.Row | None,
) -> bool:
    if status is None or revision is None or live_run is None:
        return False
    try:
        run = _load_run_locked(conn, tenant_id=tenant_id, run_id=run_id)
        if run is None:
            return False
        compiled = compile_sequential_workflow(
            run=run,
            actions=_load_actions_locked(conn, run_id=run_id),
            events=_load_events_locked(conn, run_id=run_id),
        )
    except ValueError:
        return False
    expected_task_ids = [task.task_id for task in compiled.tasks]
    actual_task_ids = [str(row["task_id"]) for row in task_rows]
    expected_edges = {
        (edge.edge_id, edge.from_task_id, edge.to_task_id, edge.join_policy)
        for edge in compiled.edges
    }
    actual_edges = {
        (
            str(row["edge_id"]),
            str(row["from_task_id"]),
            str(row["to_task_id"]),
            str(row["join_policy"]),
        )
        for row in edge_rows
    }
    expected_events = list(compiled.events)
    events_current = len(expected_events) == len(event_rows) and all(
        _stored_event_matches(row, expected, sequence=index)
        for index, (row, expected) in enumerate(zip(event_rows, expected_events))
    )
    return bool(
        status["projection_state"] == "current"
        and shadow["structural_digest"] == compiled.structural_digest
        and revision["graph_hash"] == compiled.graph_hash
        and int(status["source_action_count"])
        == int(status["projected_task_count"])
        == len(expected_task_ids)
        == len(actual_task_ids)
        and int(status["source_event_count"])
        == int(status["projected_event_count"])
        == len(expected_events)
        == len(event_rows)
        and actual_task_ids == expected_task_ids
        and actual_edges == expected_edges
        and events_current
    )


def _stored_event_matches(row: sqlite3.Row, expected: Any, *, sequence: int) -> bool:
    return (
        int(row["sequence"]) == sequence
        and row["event_id"] == expected.event_id
        and row["source_event_id"] == expected.source_event_id
        and int(row["source_row_order"]) == expected.source_row_order
        and row["event_type"] == expected.event_type
        and row["entity_type"] == expected.entity_type
        and row["entity_id"] == expected.entity_id
        and row["principal_id"] == expected.principal_id
        and row["payload_json"] == expected.payload_json
        and row["payload_hash"] == expected.payload_hash
        and row["causation_id"] == expected.causation_id
        and row["correlation_id"] == expected.correlation_id
        and row["trace_id"] == expected.trace_id
        and row["occurred_at"] == expected.occurred_at
    )


def _load_semantic_sources_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM workflow_compatibility_semantic_sources
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY artifact_type ASC, source_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()


def _import_semantic_artifacts_locked(
    conn: sqlite3.Connection, sources: list[sqlite3.Row]
) -> int:
    imported = 0
    now = _now()
    for source in sources:
        existing = conn.execute(
            """
            SELECT * FROM workflow_compatibility_semantic_artifacts
            WHERE tenant_id = ? AND workflow_id = ?
              AND artifact_type = ? AND source_id = ?
            """,
            (
                source["tenant_id"],
                source["workflow_id"],
                source["artifact_type"],
                source["source_id"],
            ),
        ).fetchone()
        if existing is not None:
            if not _semantic_artifact_matches(existing, source):
                raise ValueError(
                    "existing workflow semantic artifact disagrees with its source"
                )
            continue
        conn.execute(
            """
            INSERT INTO workflow_compatibility_semantic_artifacts (
                semantic_artifact_id, tenant_id, workflow_id, graph_revision,
                artifact_type, source_id, task_id, attempt_id, payload_json,
                payload_hash, source_recorded_at, projected_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, json(?), ?, ?, ?)
            """,
            (
                f"workflow-semantic:{source['artifact_type']}:{source['source_id']}",
                source["tenant_id"],
                source["workflow_id"],
                int(source["graph_revision"]),
                source["artifact_type"],
                source["source_id"],
                source["task_id"],
                source["attempt_id"],
                source["payload_json"],
                source["payload_hash"],
                source["recorded_at"],
                now,
            ),
        )
        imported += 1
    return imported


def _semantic_artifact_matches(stored: sqlite3.Row, source: sqlite3.Row) -> bool:
    return bool(
        stored["tenant_id"] == source["tenant_id"]
        and stored["workflow_id"] == source["workflow_id"]
        and int(stored["graph_revision"]) == int(source["graph_revision"])
        and stored["artifact_type"] == source["artifact_type"]
        and stored["source_id"] == source["source_id"]
        and stored["task_id"] == source["task_id"]
        and stored["attempt_id"] == source["attempt_id"]
        and stored["payload_json"] == source["payload_json"]
        and stored["payload_hash"] == source["payload_hash"]
        and stored["source_recorded_at"] == source["recorded_at"]
    )


def _semantic_parity_state_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    sources: list[sqlite3.Row],
) -> dict[str, Any]:
    projected = conn.execute(
        """
        SELECT * FROM workflow_compatibility_semantic_artifacts
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY artifact_type ASC, source_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    governed = conn.execute(
        """
        SELECT 1 FROM workflow_completion_governance
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    completion = _completion_projection_identity_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    exact = len(sources) == len(projected) and all(
        _semantic_artifact_matches(stored, source)
        for stored, source in zip(projected, sources)
    )
    if governed is None:
        parity_state = "not_governed"
        error_code = "completion_governance_absent"
    elif completion is None:
        parity_state = "drifted"
        error_code = "completion_projection_absent"
    elif not completion["is_current"]:
        parity_state = "drifted"
        error_code = "completion_projection_stale"
    elif not exact:
        parity_state = "drifted"
        error_code = "semantic_artifact_mismatch"
    elif not _has_current_completion_checkpoint(sources, completion=completion):
        parity_state = "drifted"
        error_code = "completion_checkpoint_mismatch"
    else:
        parity_state = "current"
        error_code = None
    return {
        "parity_state": parity_state,
        "projected_artifact_count": len(projected),
        "completion": completion,
        "error_code": error_code,
    }


def _has_current_completion_checkpoint(
    sources: list[sqlite3.Row], *, completion: dict[str, Any]
) -> bool:
    for source in sources:
        if source["artifact_type"] != "completion_checkpoint":
            continue
        try:
            payload = json.loads(source["payload_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            return False
        if (
            payload.get("decision_id") == completion["decision_id"]
            and payload.get("decision_digest") == completion["decision_digest"]
            and payload.get("authoritative_event_sequence")
            == completion["event_sequence"]
        ):
            return True
    return False


def _completion_projection_identity_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT projection.*, decision.decision_digest AS source_decision_digest
        FROM workflow_completion_projections projection
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = projection.decision_id
        WHERE projection.tenant_id = ? AND projection.workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    if row is None:
        return None
    fence = outcome_reads.get_completion_projection_fence_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    governance = conn.execute(
        """
        SELECT graph_revision, criteria_digest
        FROM workflow_completion_governance
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    event_cursor = conn.execute(
        """
        SELECT current_sequence
        FROM workflow_completion_event_cursors
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    is_current = bool(
        fence is not None
        and governance is not None
        and event_cursor is not None
        and int(row["graph_revision"]) == fence.active_graph_revision
        and int(row["graph_revision"]) == int(governance["graph_revision"])
        and row["criteria_digest"] == governance["criteria_digest"]
        and row["action_projection_digest"] == fence.action_projection_digest
        and row["projected_run_status"] == fence.run_status
        and row["projected_run_state"] == fence.run_state
        and int(row["authoritative_event_sequence"])
        == int(event_cursor["current_sequence"])
    )
    payload = {
        "action_projection_digest": row["action_projection_digest"],
        "authoritative_event_sequence": int(row["authoritative_event_sequence"]),
        "blockers": from_json(row["blockers_json"], default=[]),
        "completion_status": row["completion_status"],
        "criteria_digest": row["criteria_digest"],
        "decision_digest": row["decision_digest"],
        "decision_id": row["decision_id"],
        "evaluated_at": row["evaluated_at"],
        "graph_revision": int(row["graph_revision"]),
        "projected_run_state": row["projected_run_state"],
        "projected_run_status": row["projected_run_status"],
        "projection_version": int(row["projection_version"]),
    }
    canonical = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return {
        "decision_id": row["decision_id"],
        "decision_digest": row["source_decision_digest"],
        "event_sequence": int(row["authoritative_event_sequence"]),
        "projection_version": int(row["projection_version"]),
        "projection_hash": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "is_current": is_current,
    }


def _upsert_semantic_status_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    parity_state: str,
    source_artifact_count: int,
    projected_artifact_count: int,
    completion: dict[str, Any] | None,
    error_code: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO workflow_compatibility_semantic_status (
            tenant_id, workflow_id, parity_state, source_artifact_count,
            projected_artifact_count, completion_decision_id,
            completion_decision_digest, completion_event_sequence,
            completion_projection_version, completion_projection_hash,
            error_code, checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tenant_id, workflow_id) DO UPDATE SET
            parity_state = excluded.parity_state,
            source_artifact_count = excluded.source_artifact_count,
            projected_artifact_count = excluded.projected_artifact_count,
            completion_decision_id = excluded.completion_decision_id,
            completion_decision_digest = excluded.completion_decision_digest,
            completion_event_sequence = excluded.completion_event_sequence,
            completion_projection_version = excluded.completion_projection_version,
            completion_projection_hash = excluded.completion_projection_hash,
            error_code = excluded.error_code,
            checked_at = excluded.checked_at
        """,
        (
            tenant_id,
            workflow_id,
            parity_state,
            source_artifact_count,
            projected_artifact_count,
            None if completion is None else completion["decision_id"],
            None if completion is None else completion["decision_digest"],
            None if completion is None else completion["event_sequence"],
            None if completion is None else completion["projection_version"],
            None if completion is None else completion["projection_hash"],
            error_code,
            _now(),
        ),
    )


def _semantic_content_is_current(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    semantic_rows: list[sqlite3.Row],
    semantic_status: sqlite3.Row | None,
) -> bool:
    if semantic_status is None or semantic_status["parity_state"] != "current":
        return False
    sources = _load_semantic_sources_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    if len(sources) != len(semantic_rows):
        return False
    if not all(
        _semantic_artifact_matches(stored, source)
        for stored, source in zip(semantic_rows, sources)
    ):
        return False
    completion = _completion_projection_identity_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    if completion is None:
        return False
    if not completion["is_current"]:
        return False
    try:
        return bool(
            semantic_status["completion_decision_id"] == completion["decision_id"]
            and semantic_status["completion_decision_digest"]
            == completion["decision_digest"]
            and int(semantic_status["completion_event_sequence"])
            == completion["event_sequence"]
            and int(semantic_status["completion_projection_version"])
            == completion["projection_version"]
            and semantic_status["completion_projection_hash"]
            == completion["projection_hash"]
        )
    except (TypeError, ValueError):
        return False


def _load_run_locked(
    conn: sqlite3.Connection, *, tenant_id: str, run_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        "SELECT * FROM agent_runs WHERE id = ? AND client_id = ?",
        (run_id, tenant_id),
    ).fetchone()
    if row is None:
        return None
    for lineage_field in ("root_run_id", "parent_run_id"):
        lineage_id = row[lineage_field]
        if lineage_id is None:
            continue
        lineage = conn.execute(
            "SELECT client_id FROM agent_runs WHERE id = ?",
            (lineage_id,),
        ).fetchone()
        if lineage is None or lineage["client_id"] != tenant_id:
            raise ValueError("agent run lineage leaves the tenant scope")
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "objective": from_json(row["objective_json"], default={}),
        "allowed_capabilities": from_json(row["allowed_capabilities_json"], default=[]),
        "budgets": from_json(row["budgets_json"], default={}),
        "approval_policy": from_json(row["approval_policy_json"], default={}),
        "requires_approval": bool(row["requires_approval"]),
        "state": row["state"],
        "status": row["status"],
        "principal_type": row["principal_type"],
        "principal_id": row["principal_id"],
        "agent_profile_id": row["agent_profile_id"],
        "harness_id": row["harness_id"],
        "policy_profile_id": row["policy_profile_id"],
        "idempotency_key": row["idempotency_key"],
        "trace_id": row["trace_id"],
        "root_run_id": row["root_run_id"],
        "parent_run_id": row["parent_run_id"],
        "registry_version": row["registry_version"],
        "registry_fingerprint": row["registry_fingerprint"],
        "active_graph_revision": int(row["active_graph_revision"]),
        "created_at": row["created_at"],
    }


def _load_actions_locked(
    conn: sqlite3.Connection, *, run_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM agent_actions
        WHERE agent_run_id = ?
        ORDER BY sequence ASC, id ASC
        """,
        (run_id,),
    ).fetchall()
    return [
        {
            "id": row["id"],
            "sequence": int(row["sequence"]),
            "status": row["status"],
            "capability_name": row["capability_name"],
            "capability_version": row["capability_version"],
            "inputs": from_json(row["inputs_json"], default={}),
            "inputs_hash": row["inputs_hash"],
            "effect_class": row["effect_class"],
            "skill_id": row["skill_id"],
            "skill_version": row["skill_version"],
            "tool_id": row["tool_id"],
            "tool_version": row["tool_version"],
        }
        for row in rows
    ]


def _load_events_locked(
    conn: sqlite3.Connection, *, run_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT event.rowid AS source_row_order,
               event.*,
               action.agent_run_id AS action_owner_run_id
        FROM agent_events event
        LEFT JOIN agent_actions action ON action.id = event.action_id
        WHERE event.agent_run_id = ?
        ORDER BY event.rowid ASC
        """,
        (run_id,),
    ).fetchall()
    for row in rows:
        if row["action_id"] is not None and row["action_owner_run_id"] != run_id:
            raise ValueError("event action does not belong to the source run")
    return [
        {
            "id": row["id"],
            "source_row_order": int(row["source_row_order"]),
            "action_id": row["action_id"],
            "sequence": int(row["sequence"]),
            "event_type": row["event_type"],
            "status": row["status"],
            "capability_name": row["capability_name"],
            "capability_version": row["capability_version"],
            "principal_id": row["principal_id"],
            "tool_id": row["tool_id"],
            "skill_id": row["skill_id"],
            "effect_class": row["effect_class"],
            "note": row["note_text"],
            "is_policy_event": bool(row["is_policy_event"]),
            "anchors": from_json(row["anchors_json"], default={}),
            "timestamp": row["created_at"],
        }
        for row in rows
    ]


def _insert_structure_locked(
    conn: sqlite3.Connection, compiled: SequentialWorkflowCompatibility
) -> None:
    now = _now()
    conn.execute(
        """
        INSERT INTO workflow_compatibility_runs (
            workflow_id, tenant_id, source_agent_run_id, root_workflow_id,
            parent_workflow_id, objective_json, objective_hash, initial_status,
            initial_state, active_revision, principal_type, principal_id,
            authority_json, authority_hash, budget_json, agent_profile_id,
            harness_id, policy_profile_id, registry_version,
            registry_fingerprint, idempotency_key, request_hash, trace_id,
            source_created_at, structural_digest, created_at
        ) VALUES (?, ?, ?, ?, ?, json(?), ?, ?, ?, ?, ?, ?, json(?), ?,
                  json(?), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            compiled.workflow_id,
            compiled.tenant_id,
            compiled.source_agent_run_id,
            compiled.root_workflow_id,
            compiled.parent_workflow_id,
            compiled.objective_json,
            compiled.objective_hash,
            compiled.initial_status,
            compiled.initial_state,
            compiled.active_revision,
            compiled.principal_type,
            compiled.principal_id,
            compiled.authority_json,
            compiled.authority_hash,
            compiled.budget_json,
            compiled.agent_profile_id,
            compiled.harness_id,
            compiled.policy_profile_id,
            compiled.registry_version,
            compiled.registry_fingerprint,
            compiled.idempotency_key,
            compiled.request_hash,
            compiled.trace_id,
            compiled.source_created_at,
            compiled.structural_digest,
            now,
        ),
    )
    conn.execute(
        """
        INSERT INTO workflow_compatibility_revisions (
            tenant_id, workflow_id, revision, parent_revision, reason,
            planner_contract_version, graph_hash, created_by_principal_id,
            created_at
        ) VALUES (?, ?, 1, NULL, 'initial_plan', ?, ?, ?, ?)
        """,
        (
            compiled.tenant_id,
            compiled.workflow_id,
            compiled.planner_contract_version,
            compiled.graph_hash,
            compiled.principal_id,
            now,
        ),
    )
    for task in compiled.tasks:
        conn.execute(
            """
            INSERT INTO workflow_compatibility_tasks (
                task_id, tenant_id, workflow_id, source_action_id,
                introduced_in_revision, task_key, sequence, task_type,
                capability_version, initial_status, effect_class, skill_id,
                skill_version, tool_id, tool_version, input_json, input_hash,
                result_schema_id,
                result_schema_version, created_at
            ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?),
                      ?, ?, ?, ?)
            """,
            (
                task.task_id,
                compiled.tenant_id,
                compiled.workflow_id,
                task.source_action_id,
                task.task_key,
                task.sequence,
                task.task_type,
                task.capability_version,
                task.initial_status,
                task.effect_class,
                task.skill_id,
                task.skill_version,
                task.tool_id,
                task.tool_version,
                task.input_json,
                task.input_hash,
                task.result_schema_id,
                task.result_schema_version,
                now,
            ),
        )
        conn.execute(
            """
            INSERT INTO workflow_compatibility_revision_tasks (
                tenant_id, workflow_id, revision, task_id, disposition, reason
            ) VALUES (?, ?, 1, ?, 'active', 'initial_plan')
            """,
            (compiled.tenant_id, compiled.workflow_id, task.task_id),
        )
    for edge in compiled.edges:
        conn.execute(
            """
            INSERT INTO workflow_compatibility_edges (
                edge_id, tenant_id, workflow_id, revision, from_task_id,
                to_task_id, join_policy
            ) VALUES (?, ?, ?, 1, ?, ?, ?)
            """,
            (
                edge.edge_id,
                compiled.tenant_id,
                compiled.workflow_id,
                edge.from_task_id,
                edge.to_task_id,
                edge.join_policy,
            ),
        )


def _import_events_locked(
    conn: sqlite3.Connection, compiled: SequentialWorkflowCompatibility
) -> int:
    imported = 0
    next_sequence = int(
        conn.execute(
            """
            SELECT COALESCE(MAX(sequence), -1) + 1
            FROM workflow_compatibility_events
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            (compiled.tenant_id, compiled.workflow_id),
        ).fetchone()[0]
    )
    for event in compiled.events:
        existing = conn.execute(
            """
            SELECT source_row_order, payload_hash, event_type, entity_type,
                   entity_id, principal_id, causation_id, correlation_id,
                   trace_id, occurred_at
            FROM workflow_compatibility_events
            WHERE source_event_id = ?
            """,
            (event.source_event_id,),
        ).fetchone()
        if existing is not None:
            identity = (
                int(existing["source_row_order"]),
                existing["payload_hash"],
                existing["event_type"],
                existing["entity_type"],
                existing["entity_id"],
                existing["principal_id"],
                existing["causation_id"],
                existing["correlation_id"],
                existing["trace_id"],
                existing["occurred_at"],
            )
            expected = (
                event.source_row_order,
                event.payload_hash,
                event.event_type,
                event.entity_type,
                event.entity_id,
                event.principal_id,
                event.causation_id,
                event.correlation_id,
                event.trace_id,
                event.occurred_at,
            )
            if identity != expected:
                raise ValueError("existing workflow event disagrees with its source")
            continue
        conn.execute(
            """
            INSERT INTO workflow_compatibility_events (
                event_id, tenant_id, workflow_id, sequence, source_event_id,
                source_row_order, event_type, event_version, entity_type,
                entity_id, principal_id, command_id, event_index, payload_json,
                payload_hash, causation_id, correlation_id, trace_id,
                occurred_at, recorded_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, '1.0', ?, ?, ?, ?, ?, json(?), ?,
                      ?, ?, ?, ?, ?)
            """,
            (
                event.event_id,
                compiled.tenant_id,
                compiled.workflow_id,
                next_sequence,
                event.source_event_id,
                event.source_row_order,
                event.event_type,
                event.entity_type,
                event.entity_id,
                event.principal_id,
                f"compatibility-import:{compiled.workflow_id}",
                event.source_row_order,
                event.payload_json,
                event.payload_hash,
                event.causation_id,
                event.correlation_id,
                event.trace_id,
                event.occurred_at,
                _now(),
            ),
        )
        next_sequence += 1
        imported += 1
    return imported


def _upsert_status_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    projection_state: str,
    structural_digest: str | None,
    source_action_count: int,
    projected_task_count: int,
    source_event_count: int,
    projected_event_count: int,
    error_code: str | None,
) -> None:
    conn.execute(
        """
        INSERT INTO workflow_compatibility_projection_status (
            tenant_id, workflow_id, projection_state, structural_digest,
            source_action_count, projected_task_count, source_event_count,
            projected_event_count, error_code, checked_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(tenant_id, workflow_id) DO UPDATE SET
            projection_state = excluded.projection_state,
            structural_digest = excluded.structural_digest,
            source_action_count = excluded.source_action_count,
            projected_task_count = excluded.projected_task_count,
            source_event_count = excluded.source_event_count,
            projected_event_count = excluded.projected_event_count,
            error_code = excluded.error_code,
            checked_at = excluded.checked_at
        """,
        (
            tenant_id,
            workflow_id,
            projection_state,
            structural_digest,
            source_action_count,
            projected_task_count,
            source_event_count,
            projected_event_count,
            error_code,
            _now(),
        ),
    )


def _count_locked(
    conn: sqlite3.Connection, table: str, tenant_id: str, workflow_id: str
) -> int:
    allowed = {
        "workflow_compatibility_revision_tasks",
        "workflow_compatibility_events",
    }
    if table not in allowed:
        raise ValueError("unsupported compatibility table")
    return int(
        conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE tenant_id = ? AND workflow_id = ?",
            (tenant_id, workflow_id),
        ).fetchone()[0]
    )


def _dict_row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _event_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json"))
    return result


def _semantic_row(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    result["payload"] = json.loads(result.pop("payload_json"))
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "get_sequential_projection",
    "list_projection_candidates",
    "project_sequential_run",
    "record_projection_failure",
]
