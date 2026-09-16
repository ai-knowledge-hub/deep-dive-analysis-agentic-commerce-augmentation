"""Read and reconstruct exact workflow outcome ledger artifacts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from typing import Any

from domain.workflow.outcome_lifecycle import (
    CompletionProjectionFence,
    TaskAttemptAuthority,
)
from domain.workflow.outcomes import ResultValidationStatus, evidence_set_digest
from infrastructure.db.workflow.outcome_rows import (
    OutcomeLedgerDataError,
    authority_snapshot_record,
    criteria_record,
    decision_record,
    evidence_record,
    task_result_record,
)


def get_evidence_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    evidence_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_evidence_records
        WHERE tenant_id = ? AND workflow_id = ? AND evidence_id = ?
        """,
        (tenant_id, workflow_id, evidence_id),
    ).fetchone()
    return _evidence_with_command(conn, row) if row else None


def get_evidence_by_digest_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    evidence_digest: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_evidence_records
        WHERE tenant_id = ? AND workflow_id = ? AND evidence_digest = ?
        """,
        (tenant_id, workflow_id, evidence_digest),
    ).fetchone()
    return _evidence_with_command(conn, row) if row else None


def get_task_result_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    result_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_task_results
        WHERE tenant_id = ? AND workflow_id = ? AND result_id = ?
        """,
        (tenant_id, workflow_id, result_id),
    ).fetchone()
    return _task_result_with_evidence(conn, row) if row else None


def get_task_result_by_digest_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    result_digest: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_task_results
        WHERE tenant_id = ? AND workflow_id = ? AND result_digest = ?
        """,
        (tenant_id, workflow_id, result_digest),
    ).fetchone()
    return _task_result_with_evidence(conn, row) if row else None


def list_accepted_task_results_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    graph_revision: int,
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM workflow_task_results
        WHERE tenant_id = ? AND workflow_id = ? AND graph_revision = ?
          AND validation_status = 'accepted'
        ORDER BY task_id ASC, result_id ASC
        """,
        (tenant_id, workflow_id, graph_revision),
    ).fetchall()
    return [_task_result_with_evidence(conn, row) for row in rows]


def get_completion_contract_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    criteria_id: str,
    criteria_hash: str | None = None,
) -> dict[str, Any] | None:
    if criteria_hash is None:
        row = conn.execute(
            """
            SELECT * FROM workflow_completion_criteria
            WHERE tenant_id = ? AND workflow_id = ? AND criteria_id = ?
            ORDER BY created_at DESC, criteria_digest DESC
            LIMIT 1
            """,
            (tenant_id, workflow_id, criteria_id),
        ).fetchone()
    else:
        row = conn.execute(
            """
            SELECT * FROM workflow_completion_criteria
            WHERE tenant_id = ? AND workflow_id = ?
              AND criteria_id = ? AND criteria_digest = ?
            """,
            (tenant_id, workflow_id, criteria_id, criteria_hash),
        ).fetchone()
    if row is None:
        return None
    definitions = conn.execute(
        """
        SELECT * FROM workflow_completion_task_definitions
        WHERE criteria_digest = ? ORDER BY task_id ASC
        """,
        (row["criteria_digest"],),
    ).fetchall()
    publication = criteria_record(row, list(definitions))
    criteria = publication["criteria"]
    _verify_command_binding(
        conn,
        artifact_row=row,
        command_type="publish_completion_contract",
        artifact_type="completion_contract",
        artifact_id=criteria.criteria_id,
        artifact_digest=publication["criteria_digest"],
        request={
            "criteria_hash": publication["criteria_digest"],
            "task_definitions_hash": _definitions_digest(
                publication["task_definitions"]
            ),
        },
        authority=(
            criteria.publishing_authority.principal_id,
            criteria.publishing_authority.authority_source,
            criteria.publishing_authority.authority_version,
        ),
    )
    return publication


def get_authority_snapshot_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    snapshot_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_completion_authority_snapshots
        WHERE tenant_id = ? AND workflow_id = ? AND snapshot_id = ?
        """,
        (tenant_id, workflow_id, snapshot_id),
    ).fetchone()
    if row is None:
        return None
    publication = get_completion_contract_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        criteria_id=row["criteria_id"],
        criteria_hash=row["criteria_digest"],
    )
    if publication is None:
        raise OutcomeLedgerDataError("snapshot completion contract is missing")
    result_rows = conn.execute(
        """
        SELECT * FROM workflow_completion_snapshot_results
        WHERE snapshot_id = ? ORDER BY task_id ASC
        """,
        (snapshot_id,),
    ).fetchall()
    snapshot = authority_snapshot_record(
        row, publication=publication, result_rows=list(result_rows)
    )
    value = snapshot["snapshot"]
    _verify_command_binding(
        conn,
        artifact_row=row,
        command_type="issue_authority_snapshot",
        artifact_type="authority_snapshot",
        artifact_id=snapshot_id,
        artifact_digest=snapshot["snapshot_digest"],
        request={
            "snapshot_id": snapshot_id,
            "snapshot_digest": snapshot["snapshot_digest"],
        },
        authority=(
            value.evaluation_authority.principal_id,
            value.evaluation_authority.authority_source,
            value.evaluation_authority.authority_version,
        ),
    )
    resolved_results = []
    for binding in result_rows:
        result = get_task_result_by_digest_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            result_digest=binding["result_digest"],
        )
        if (
            result is None
            or result["result"].result_id != binding["result_id"]
            or result["result"].task_id != binding["task_id"]
        ):
            raise OutcomeLedgerDataError(
                "snapshot result binding does not resolve exactly"
            )
        resolved_results.append(result)
    return {**snapshot, "results": resolved_results}


def get_completion_decision_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    decision_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_completion_decisions
        WHERE tenant_id = ? AND workflow_id = ? AND decision_id = ?
        """,
        (tenant_id, workflow_id, decision_id),
    ).fetchone()
    if row is None:
        return None
    decision = decision_record(row)
    value = decision["decision"]
    lifecycle = conn.execute(
        """
        SELECT projected_run_state FROM workflow_completion_lifecycle_events
        WHERE tenant_id = ? AND workflow_id = ? AND decision_id = ?
        """,
        (tenant_id, workflow_id, decision_id),
    ).fetchone()
    _verify_command_binding(
        conn,
        artifact_row=row,
        command_type="record_completion_decision",
        artifact_type="completion_decision",
        artifact_id=value.decision_id,
        artifact_digest=decision["decision_digest"],
        request={
            "snapshot_id": decision["snapshot_id"],
            "snapshot_digest": decision["snapshot_digest"],
            "decision_digest": decision["decision_digest"],
            "projected_run_state": (
                lifecycle["projected_run_state"] if lifecycle is not None else None
            ),
        },
        authority=(
            value.evaluation_authority.principal_id,
            value.evaluation_authority.authority_source,
            value.evaluation_authority.authority_version,
        ),
    )
    return decision


def get_completion_projection_fence_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
) -> CompletionProjectionFence | None:
    """Read the exact compatibility projection used as the completion CAS."""

    run = conn.execute(
        """
        SELECT state, status, active_graph_revision,
               CASE
                 WHEN lock_token IS NOT NULL
                  AND lock_expires_at IS NOT NULL
                  AND lock_expires_at > datetime('now')
                 THEN lock_token
                 ELSE NULL
               END AS active_lock_token
        FROM agent_runs
        WHERE client_id = ? AND id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    if run is None:
        return None
    return CompletionProjectionFence(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        active_graph_revision=int(run["active_graph_revision"]),
        run_status=str(run["status"]),
        run_state=str(run["state"]),
        active_lock_token=run["active_lock_token"],
        action_projection_digest=_action_projection_digest(conn, workflow_id),
    )


def get_active_completion_contract_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT criteria.criteria_id, governance.criteria_digest
        FROM workflow_completion_governance governance
        JOIN workflow_completion_criteria criteria
          ON criteria.criteria_digest = governance.criteria_digest
        WHERE governance.tenant_id = ? AND governance.workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    if row is None:
        return None
    return get_completion_contract_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        criteria_id=row["criteria_id"],
        criteria_hash=row["criteria_digest"],
    )


def get_task_attempt_authority_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    task_id: str,
) -> TaskAttemptAuthority | None:
    row = conn.execute(
        """
        SELECT authority.graph_revision, authority.task_id, authority.attempt_id,
               authority.assignment_id, authority.producer_principal_id,
               authority.action_id, run.lock_token
        FROM workflow_completion_attempt_authorities authority
        JOIN agent_runs run
          ON run.client_id = authority.tenant_id
         AND run.id = authority.workflow_id
        JOIN agent_actions action
          ON action.id = authority.action_id
         AND action.agent_run_id = authority.workflow_id
        WHERE authority.tenant_id = ?
          AND authority.workflow_id = ?
          AND authority.task_id = ?
          AND action.status = 'executed'
          AND run.active_graph_revision = authority.graph_revision
          AND run.lock_token IS NOT NULL
          AND run.lock_expires_at > datetime('now')
        """,
        (tenant_id, workflow_id, task_id),
    ).fetchone()
    if row is None:
        return None
    return TaskAttemptAuthority(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        graph_revision=int(row["graph_revision"]),
        task_id=row["task_id"],
        attempt_id=row["attempt_id"],
        assignment_id=row["assignment_id"],
        producer_principal_id=row["producer_principal_id"],
        action_id=row["action_id"],
        active_lock_token=row["lock_token"],
    )


def get_completion_projection_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_completion_projections
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    if row is None:
        return None
    return {
        "tenant_id": row["tenant_id"],
        "workflow_id": row["workflow_id"],
        "graph_revision": int(row["graph_revision"]),
        "decision_id": row["decision_id"],
        "decision_digest": row["decision_digest"],
        "criteria_digest": row["criteria_digest"],
        "completion_status": row["completion_status"],
        "projected_run_status": row["projected_run_status"],
        "projected_run_state": row["projected_run_state"],
        "authoritative_event_sequence": int(row["authoritative_event_sequence"]),
        "action_projection_digest": row["action_projection_digest"],
        "blockers": json.loads(row["blockers_json"]),
        "evaluated_at": row["evaluated_at"],
        "projection_version": int(row["projection_version"]),
        "updated_at": row["updated_at"],
    }


def resolve_completion_event_sequence_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    idempotency_key: str,
    decision_id: str,
) -> int:
    """Return a replay sequence or the next host-owned lifecycle sequence."""

    replay = conn.execute(
        """
        SELECT decision.authoritative_event_sequence
        FROM workflow_outcome_commands command
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = command.artifact_id
        WHERE command.tenant_id = ?
          AND command.workflow_id = ?
          AND command.idempotency_key = ?
          AND command.artifact_type = 'completion_decision'
          AND command.artifact_id = ?
        """,
        (tenant_id, workflow_id, idempotency_key, decision_id),
    ).fetchone()
    if replay is not None:
        return int(replay["authoritative_event_sequence"])
    cursor = conn.execute(
        """
        SELECT current_sequence
        FROM workflow_completion_event_cursors
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    return (int(cursor["current_sequence"]) if cursor is not None else -1) + 1


def _action_projection_digest(conn: sqlite3.Connection, workflow_id: str) -> str:
    rows = conn.execute(
        """
        SELECT id, sequence, status, capability_name, outputs_json, outputs_hash,
               error_text
        FROM agent_actions
        WHERE agent_run_id = ?
        ORDER BY sequence ASC, id ASC
        """,
        (workflow_id,),
    ).fetchall()
    projection = [
        {
            "id": row["id"],
            "sequence": int(row["sequence"]),
            "status": row["status"],
            "capability_name": row["capability_name"],
            "outputs_hash": _stored_output_hash(row),
            "error": row["error_text"],
        }
        for row in rows
    ]
    encoded = json.dumps(
        projection,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _stored_output_hash(row) -> str:
    payload = json.loads(row["outputs_json"] or "{}")
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_evaluation_bundle_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    decision_id: str,
) -> dict[str, Any] | None:
    decision = get_completion_decision_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        decision_id=decision_id,
    )
    if decision is None:
        return None
    snapshot = get_authority_snapshot_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        snapshot_id=decision["snapshot_id"],
    )
    if snapshot is None or snapshot["snapshot_digest"] != decision["snapshot_digest"]:
        raise OutcomeLedgerDataError("decision authority snapshot is unavailable")
    criteria = get_completion_contract_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        criteria_id=snapshot["snapshot"].criteria_id,
        criteria_hash=snapshot["snapshot"].criteria_hash,
    )
    if criteria is None:
        raise OutcomeLedgerDataError("decision completion criteria are unavailable")
    result_rows = conn.execute(
        """
        SELECT result_id, result_digest
        FROM workflow_completion_decision_results
        WHERE decision_id = ? ORDER BY result_id ASC
        """,
        (decision_id,),
    ).fetchall()
    results = []
    for row in result_rows:
        result = get_task_result_by_digest_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            result_digest=row["result_digest"],
        )
        if result is None or result["result"].result_id != row["result_id"]:
            raise OutcomeLedgerDataError(
                "decision result binding does not resolve exactly"
            )
        results.append(result)
    evidence_rows = conn.execute(
        """
        SELECT evidence_id, evidence_digest
        FROM workflow_completion_decision_evidence
        WHERE decision_id = ? ORDER BY evidence_id ASC
        """,
        (decision_id,),
    ).fetchall()
    evidence = []
    for row in evidence_rows:
        item = get_evidence_by_digest_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            evidence_digest=row["evidence_digest"],
        )
        if item is None or item["evidence"].evidence_id != row["evidence_id"]:
            raise OutcomeLedgerDataError(
                "decision evidence binding does not resolve exactly"
            )
        evidence.append(item)
    persisted = decision["decision"]
    if tuple(row["result_id"] for row in result_rows) != persisted.accepted_result_ids:
        raise OutcomeLedgerDataError(
            "decision result bindings do not match its canonical payload"
        )
    if tuple(row["evidence_id"] for row in evidence_rows) != persisted.evidence_ids:
        raise OutcomeLedgerDataError(
            "decision evidence bindings do not match its canonical payload"
        )
    snapshot_bindings = {
        (item["result"].result_id, item["result_digest"])
        for item in snapshot["results"]
    }
    decision_bindings = {
        (row["result_id"], row["result_digest"]) for row in result_rows
    }
    if decision_bindings != snapshot_bindings:
        raise OutcomeLedgerDataError(
            "decision results do not match its authority snapshot"
        )
    expected_evidence_bindings = {
        (item["evidence"].evidence_id, item["evidence_digest"])
        for result in results
        for item in result["evidence"]
    }
    decision_evidence_bindings = {
        (row["evidence_id"], row["evidence_digest"]) for row in evidence_rows
    }
    if decision_evidence_bindings != expected_evidence_bindings:
        raise OutcomeLedgerDataError(
            "decision evidence does not match exact result evidence bindings"
        )
    return {
        **decision,
        "criteria": criteria["criteria"],
        "task_definitions": criteria["task_definitions"],
        "snapshot": snapshot["snapshot"],
        "results": results,
        "evidence": evidence,
    }


def _task_result_with_evidence(
    conn: sqlite3.Connection, row: sqlite3.Row
) -> dict[str, Any]:
    record = task_result_record(row)
    result = record["result"]
    if result.validation_status is ResultValidationStatus.PENDING:
        authority = None
        principal_id = result.producer_principal_id
    else:
        value = result.validation_authority
        if value is None:
            raise OutcomeLedgerDataError("validated result authority is unavailable")
        authority = (
            value.principal_id,
            value.authority_source,
            value.authority_version,
        )
        principal_id = None
    _verify_command_binding(
        conn,
        artifact_row=row,
        command_type="record_task_result",
        artifact_type="task_result",
        artifact_id=result.result_id,
        artifact_digest=record["result_digest"],
        request={"result_digest": record["result_digest"]},
        authority=authority,
        principal_id=principal_id,
    )
    bindings = conn.execute(
        """
        SELECT evidence_id, evidence_digest
        FROM workflow_result_evidence
        WHERE result_id = ? ORDER BY evidence_id ASC
        """,
        (result.result_id,),
    ).fetchall()
    if tuple(item["evidence_id"] for item in bindings) != result.evidence_ids:
        raise OutcomeLedgerDataError(
            "result evidence bindings do not match its canonical payload"
        )
    evidence = []
    for binding in bindings:
        item = conn.execute(
            """
            SELECT * FROM workflow_evidence_records
            WHERE tenant_id = ? AND workflow_id = ?
              AND evidence_id = ? AND evidence_digest = ?
            """,
            (
                result.tenant_id,
                result.workflow_id,
                binding["evidence_id"],
                binding["evidence_digest"],
            ),
        ).fetchone()
        if item is None:
            raise OutcomeLedgerDataError(
                "result evidence binding does not resolve exactly"
            )
        evidence.append(_evidence_with_command(conn, item))
    if result.evidence_digest != evidence_set_digest(
        tuple(item["evidence"] for item in evidence)
    ):
        raise OutcomeLedgerDataError(
            "result evidence binding set does not match its canonical digest"
        )
    return {**record, "evidence": evidence}


def _evidence_with_command(
    conn: sqlite3.Connection, row: sqlite3.Row
) -> dict[str, Any]:
    record = evidence_record(row)
    evidence = record["evidence"]
    _verify_command_binding(
        conn,
        artifact_row=row,
        command_type="record_evidence",
        artifact_type="evidence",
        artifact_id=evidence.evidence_id,
        artifact_digest=record["evidence_digest"],
        request={"evidence_digest": record["evidence_digest"]},
        principal_id=evidence.provenance.producer_principal_id,
    )
    return record


def _verify_command_binding(
    conn: sqlite3.Connection,
    *,
    artifact_row: sqlite3.Row,
    command_type: str,
    artifact_type: str,
    artifact_id: str,
    artifact_digest: str,
    request: dict[str, object],
    authority: tuple[str, str, str] | None = None,
    principal_id: str | None = None,
) -> None:
    command = conn.execute(
        "SELECT * FROM workflow_outcome_commands WHERE command_id = ?",
        (artifact_row["command_id"],),
    ).fetchone()
    if command is None:
        raise OutcomeLedgerDataError("artifact command receipt is unavailable")
    expected = (
        artifact_row["tenant_id"],
        artifact_row["workflow_id"],
        command_type,
        artifact_type,
        artifact_id,
        artifact_digest,
        _request_hash(command_type, request),
    )
    actual = (
        command["tenant_id"],
        command["workflow_id"],
        command["command_type"],
        command["artifact_type"],
        command["artifact_id"],
        command["artifact_digest"],
        command["request_hash"],
    )
    if actual != expected:
        raise OutcomeLedgerDataError(
            "artifact command receipt does not match its canonical write"
        )
    if (
        authority is not None
        and (
            command["principal_id"],
            command["authority_source"],
            command["authority_version"],
        )
        != authority
    ):
        raise OutcomeLedgerDataError(
            "artifact command authority does not match its canonical payload"
        )
    if principal_id is not None and command["principal_id"] != principal_id:
        raise OutcomeLedgerDataError(
            "artifact command principal does not match its canonical payload"
        )


def _definitions_digest(definitions: tuple[object, ...]) -> str:
    return _json_digest(
        [
            {
                "task_id": item.task_id,
                "task_input_hash": item.task_input_hash,
                "result_schema_id": item.result_schema_id,
                "result_schema_version": item.result_schema_version,
                "result_schema_hash": item.result_schema_hash,
            }
            for item in definitions
        ]
    )


def _request_hash(command_type: str, request: dict[str, object]) -> str:
    return _json_digest({"command_type": command_type, "request": request})


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "get_authority_snapshot_locked",
    "get_completion_contract_locked",
    "get_completion_decision_locked",
    "get_evidence_by_digest_locked",
    "get_evidence_locked",
    "get_task_result_by_digest_locked",
    "get_task_result_locked",
    "list_accepted_task_results_locked",
    "load_evaluation_bundle_locked",
]
