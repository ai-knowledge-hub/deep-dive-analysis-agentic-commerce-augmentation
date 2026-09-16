"""Verified operational reads and idempotent repair for completion projections."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from domain.workflow.outcome_evaluation import evaluate_completion
from domain.workflow.outcome_serialization import completion_decision_digest
from infrastructure.db.workflow.outcome_reads import (
    get_completion_projection_fence_locked,
    get_completion_projection_locked,
    load_evaluation_bundle_locked,
)
from infrastructure.db.workflow.outcome_rows import (
    OutcomeLedgerDataError,
    canonical_json,
)


REPAIR_SCOPE = "completion_projections:repair"
REPAIR_AUTHORITY_SOURCE = "agent-principal-token"
REPAIR_AUTHORITY_VERSION = "agent-principal-signing-secret:v1"


def get_completion_operational_view(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> dict[str, Any] | None:
    run = conn.execute(
        "SELECT * FROM agent_runs WHERE client_id = ? AND id = ?",
        (tenant_id, workflow_id),
    ).fetchone()
    if run is None:
        return None
    governance = conn.execute(
        """
        SELECT * FROM workflow_completion_governance
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    last_repair = _last_repair(conn, tenant_id, workflow_id)
    if governance is None:
        return {
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "completion_authority_required": False,
            "authority_state": "legacy",
            "authoritative_decision": None,
            "accepted_results": [],
            "evidence": [],
            "projection": {
                "state": "not_governed",
                "freshness": "not_governed",
                "display_status": "not_governed",
                "authoritative_event_sequence": None,
                "decision_event_sequence": None,
                "projected_event_sequence": None,
                "projection_lag": None,
                "projection_version": None,
            },
            "repair": {
                "eligible": False,
                "reason": "not_governed",
                "last_outcome": last_repair,
            },
        }

    lifecycle = _latest_lifecycle_event(conn, tenant_id, workflow_id)
    projection = get_completion_projection_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    cursor = conn.execute(
        """
        SELECT current_sequence FROM workflow_completion_event_cursors
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    if lifecycle is None:
        if projection is not None or cursor is not None:
            raise OutcomeLedgerDataError(
                "completion projection or cursor exists without lifecycle authority"
            )
        return {
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "completion_authority_required": True,
            "authority_state": "awaiting_decision",
            "active_graph_revision": int(governance["graph_revision"]),
            "active_criteria_digest": governance["criteria_digest"],
            "authoritative_decision": None,
            "accepted_results": [],
            "evidence": [],
            "projection": {
                "state": "missing",
                "freshness": "stale",
                "display_status": "stale",
                "authoritative_event_sequence": None,
                "decision_event_sequence": None,
                "projected_event_sequence": None,
                "projection_lag": None,
                "projection_version": None,
            },
            "repair": {
                "eligible": False,
                "reason": "no_authoritative_decision",
                "last_outcome": last_repair,
            },
        }

    bundle = _verified_bundle(conn, tenant_id, workflow_id, lifecycle)
    decision = bundle["decision"]
    if cursor is None or int(cursor["current_sequence"]) != int(
        lifecycle["authoritative_event_sequence"]
    ):
        raise OutcomeLedgerDataError(
            "completion event cursor does not match latest immutable lifecycle event"
        )
    if (
        int(governance["graph_revision"]),
        governance["criteria_digest"],
    ) != (decision.graph_revision, decision.criteria_hash):
        raise OutcomeLedgerDataError(
            "active completion governance does not match latest decision"
        )

    fence = get_completion_projection_fence_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    if fence is None:
        raise OutcomeLedgerDataError(
            "governed workflow projection fence is unavailable"
        )
    live_matches = (
        fence.active_graph_revision == decision.graph_revision
        and fence.action_projection_digest == lifecycle["action_projection_digest"]
        and fence.run_status == lifecycle["projected_run_status"]
        and fence.run_state == lifecycle["projected_run_state"]
    )
    projection_state = _projection_state(projection, lifecycle, decision)
    is_current = projection_state == "current" and live_matches
    if projection_state == "current" and not live_matches:
        projection_state = "stale"
    projected_sequence = (
        projection["authoritative_event_sequence"] if projection is not None else None
    )
    authoritative_sequence = int(cursor["current_sequence"])
    decision_sequence = decision.authoritative_event_sequence
    lag = (
        decision_sequence - int(projected_sequence)
        if projected_sequence is not None
        else None
    )
    repair_eligible = not is_current and live_matches
    repair_reason = (
        "projection_current"
        if is_current
        else "projection_rebuild_available"
        if repair_eligible
        else "authoritative_state_changed"
    )
    decision_payload = decision.canonical_payload()
    return {
        "tenant_id": tenant_id,
        "workflow_id": workflow_id,
        "completion_authority_required": True,
        "authority_state": "current" if live_matches else "superseded",
        "active_graph_revision": int(governance["graph_revision"]),
        "active_criteria_digest": governance["criteria_digest"],
        "authoritative_decision": {
            "decision_id": decision.decision_id,
            "decision_digest": bundle["decision_digest"],
            "scope": {
                "tenant_id": decision.tenant_id,
                "workflow_id": decision.workflow_id,
                "graph_revision": decision.graph_revision,
            },
            "criteria_id": decision.criteria_id,
            "criteria_digest": decision.criteria_hash,
            "status": decision.status.value,
            "evaluated_at": decision_payload["evaluated_at"],
            "authoritative_event_sequence": decision.authoritative_event_sequence,
            "accepted_result_ids": list(decision.accepted_result_ids),
            "evidence_ids": list(decision.evidence_ids),
            "blockers": decision_payload["blockers"],
            "missing_requirements": list(decision.missing_requirement_ids),
            "partial_failures": {
                "missing_result_task_ids": list(decision.missing_result_task_ids),
                "partial_task_ids": list(decision.partial_task_ids),
                "failed_task_ids": list(decision.failed_task_ids),
                "canceled_task_ids": list(decision.canceled_task_ids),
            },
            "receipt_blockers": list(decision.unverified_evidence_ids),
        },
        "accepted_results": [
            {
                "result_id": item["result"].result_id,
                "task_id": item["result"].task_id,
                "attempt_id": item["result"].attempt_id,
                "outcome": item["result"].outcome.value,
                "validation_status": item["result"].validation_status.value,
                "result_digest": item["result_digest"],
            }
            for item in bundle["results"]
        ],
        "evidence": [
            {
                "evidence_id": item["evidence"].evidence_id,
                "task_id": item["evidence"].task_id,
                "attempt_id": item["evidence"].attempt_id,
                "availability": item["evidence"].availability.value,
                "source_type": item["evidence"].provenance.source_type,
                "source_id": item["evidence"].provenance.source_id,
                "receipt_status": item["evidence"].receipt_status.value,
                "evidence_digest": item["evidence_digest"],
            }
            for item in bundle["evidence"]
        ],
        "projection": {
            "state": projection_state,
            "freshness": "current" if is_current else "stale",
            "display_status": (decision.status.value if is_current else "stale"),
            "authoritative_event_sequence": authoritative_sequence,
            "decision_event_sequence": decision_sequence,
            "projected_event_sequence": projected_sequence,
            "projection_lag": lag,
            "projection_version": (
                projection["projection_version"] if projection is not None else None
            ),
        },
        "repair": {
            "eligible": repair_eligible,
            "reason": repair_reason,
            "last_outcome": last_repair,
        },
    }


def repair_completion_projection(
    conn: sqlite3.Connection, *, command: dict[str, Any]
) -> dict[str, Any]:
    _validate_repair_command(command)
    request_hash = _repair_request_hash(command["tenant_id"], command["workflow_id"])
    try:
        conn.execute("BEGIN IMMEDIATE")
        replay = _repair_replay(conn, command, request_hash)
        if replay is not None:
            conn.commit()
            return replay
        _require_repair_principal(conn, command)
        view = get_completion_operational_view(
            conn,
            tenant_id=command["tenant_id"],
            workflow_id=command["workflow_id"],
        )
        if view is None:
            raise OutcomeLedgerDataError("completion workflow does not exist")
        decision = view["authoritative_decision"]
        if decision is None:
            raise OutcomeLedgerDataError("no authoritative decision is available")
        if not view["repair"]["eligible"] and view["projection"]["state"] != "current":
            raise OutcomeLedgerDataError(view["repair"]["reason"])
        lifecycle = _latest_lifecycle_event(
            conn, command["tenant_id"], command["workflow_id"]
        )
        if lifecycle is None:
            raise OutcomeLedgerDataError("completion lifecycle event is unavailable")
        prior = get_completion_projection_locked(
            conn,
            tenant_id=command["tenant_id"],
            workflow_id=command["workflow_id"],
        )
        prior_version = prior["projection_version"] if prior is not None else None
        if view["projection"]["state"] == "current":
            outcome = "already_current"
            resulting_version = int(prior_version)
        else:
            resulting_version = int(prior_version or 0) + 1
            outcome = "repaired"
        completed_at = _format_utc(datetime.now(timezone.utc))
        _append_repair_audit_event(
            conn,
            command=command,
            request_hash=request_hash,
            outcome=outcome,
            lifecycle=lifecycle,
            decision=decision,
            prior_version=prior_version,
            resulting_version=resulting_version,
            completed_at=completed_at,
        )
        conn.execute(
            """
            INSERT INTO workflow_completion_projection_repairs (
                command_id, tenant_id, workflow_id, principal_type, principal_id,
                authority_source, authority_version, idempotency_key, request_hash,
                outcome, lifecycle_event_id, decision_id, decision_digest,
                authoritative_event_sequence, prior_projection_version,
                resulting_projection_version, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command["command_id"],
                command["tenant_id"],
                command["workflow_id"],
                command["principal_type"],
                command["principal_id"],
                command["authority_source"],
                command["authority_version"],
                command["idempotency_key"],
                request_hash,
                outcome,
                lifecycle["event_id"],
                decision["decision_id"],
                decision["decision_digest"],
                int(lifecycle["authoritative_event_sequence"]),
                prior_version,
                resulting_version,
                completed_at,
            ),
        )
        if outcome == "repaired":
            _replace_projection(
                conn,
                lifecycle=lifecycle,
                decision=decision,
                resulting_version=resulting_version,
                updated_at=completed_at,
            )
        conn.commit()
        return {
            "outcome": outcome,
            "command_id": command["command_id"],
            "decision_id": decision["decision_id"],
            "decision_digest": decision["decision_digest"],
            "projection_version": resulting_version,
        }
    except (
        OutcomeLedgerDataError,
        sqlite3.IntegrityError,
        sqlite3.OperationalError,
    ) as exc:
        conn.rollback()
        return {"outcome": "conflict", "reason": str(exc)}


def _verified_bundle(conn, tenant_id, workflow_id, lifecycle):
    bundle = load_evaluation_bundle_locked(
        conn,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        decision_id=lifecycle["decision_id"],
    )
    if bundle is None:
        raise OutcomeLedgerDataError("completion lifecycle decision is unavailable")
    persisted = bundle["decision"]
    reproduced = evaluate_completion(
        decision_id=persisted.decision_id,
        criteria=bundle["criteria"],
        authority_snapshot=bundle["snapshot"],
        results=tuple(item["result"] for item in bundle["results"]),
        evidence=tuple(item["evidence"] for item in bundle["evidence"]),
        evaluated_at=persisted.evaluated_at,
        authoritative_event_sequence=persisted.authoritative_event_sequence,
    )
    digest = completion_decision_digest(reproduced)
    expected = (
        persisted.decision_id,
        digest,
        persisted.tenant_id,
        persisted.workflow_id,
        persisted.graph_revision,
        persisted.status.value,
        persisted.authoritative_event_sequence,
        bundle["command_id"],
    )
    actual = (
        lifecycle["decision_id"],
        lifecycle["decision_digest"],
        lifecycle["tenant_id"],
        lifecycle["workflow_id"],
        int(lifecycle["graph_revision"]),
        lifecycle["completion_status"],
        int(lifecycle["authoritative_event_sequence"]),
        lifecycle["command_id"],
    )
    if actual != expected:
        raise OutcomeLedgerDataError(
            "completion lifecycle event does not match reproduced decision"
        )
    return bundle


def _latest_lifecycle_event(conn, tenant_id, workflow_id):
    return conn.execute(
        """
        SELECT * FROM workflow_completion_lifecycle_events
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY authoritative_event_sequence DESC LIMIT 1
        """,
        (tenant_id, workflow_id),
    ).fetchone()


def _projection_state(projection, lifecycle, decision) -> str:
    if projection is None:
        return "missing"
    expected = (
        decision.graph_revision,
        decision.decision_id,
        lifecycle["decision_digest"],
        decision.criteria_hash,
        decision.status.value,
        lifecycle["projected_run_status"],
        lifecycle["projected_run_state"],
        decision.authoritative_event_sequence,
        lifecycle["action_projection_digest"],
        decision.canonical_payload()["blockers"],
    )
    actual = (
        projection["graph_revision"],
        projection["decision_id"],
        projection["decision_digest"],
        projection["criteria_digest"],
        projection["completion_status"],
        projection["projected_run_status"],
        projection["projected_run_state"],
        projection["authoritative_event_sequence"],
        projection["action_projection_digest"],
        projection["blockers"],
    )
    if actual == expected:
        return "current"
    sequence = int(projection["authoritative_event_sequence"])
    if sequence < decision.authoritative_event_sequence:
        return "lagging"
    if sequence > decision.authoritative_event_sequence:
        return "leading"
    return "corrupt"


def _replace_projection(conn, *, lifecycle, decision, resulting_version, updated_at):
    conn.execute(
        """
        INSERT INTO workflow_completion_projections (
            tenant_id, workflow_id, graph_revision, decision_id, decision_digest,
            criteria_digest, completion_status, projected_run_status,
            projected_run_state, authoritative_event_sequence,
            action_projection_digest, blockers_json, evaluated_at,
            projection_version, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            projection_version = excluded.projection_version,
            updated_at = excluded.updated_at
        """,
        (
            decision["scope"]["tenant_id"],
            decision["scope"]["workflow_id"],
            decision["scope"]["graph_revision"],
            decision["decision_id"],
            decision["decision_digest"],
            decision["criteria_digest"],
            decision["status"],
            lifecycle["projected_run_status"],
            lifecycle["projected_run_state"],
            decision["authoritative_event_sequence"],
            lifecycle["action_projection_digest"],
            canonical_json(decision["blockers"]),
            decision["evaluated_at"],
            resulting_version,
            updated_at,
        ),
    )


def _require_repair_principal(conn, command):
    row = conn.execute(
        """
        SELECT principal.principal_type, principal.tenant_id, principal.status,
               principal.metadata_json, run.principal_id AS run_principal_id
        FROM principals principal
        JOIN agent_runs run
          ON run.client_id = principal.tenant_id
         AND run.id = ?
        WHERE principal.id = ?
        """,
        (command["workflow_id"], command["principal_id"]),
    ).fetchone()
    if row is None:
        raise OutcomeLedgerDataError("repair principal is not registered")
    metadata = json.loads(row["metadata_json"] or "{}")
    scopes = set(metadata.get("scopes") or [])
    if (
        row["principal_type"] != "human"
        or row["tenant_id"] != command["tenant_id"]
        or str(row["status"]).lower() != "active"
        or metadata.get("auth_method") != "bearer_token"
        or (REPAIR_SCOPE not in scopes and "*" not in scopes)
        or (
            row["run_principal_id"] != command["principal_id"]
            and "agent_runs:supervise" not in scopes
            and "*" not in scopes
        )
    ):
        raise OutcomeLedgerDataError(
            "repair principal lacks durable operator authority"
        )


def _repair_replay(conn, command, request_hash):
    row = conn.execute(
        """
        SELECT * FROM workflow_completion_projection_repairs
        WHERE tenant_id = ? AND workflow_id = ? AND idempotency_key = ?
        """,
        (command["tenant_id"], command["workflow_id"], command["idempotency_key"]),
    ).fetchone()
    if row is None:
        return None
    expected = (
        command["principal_type"],
        command["principal_id"],
        command["authority_source"],
        command["authority_version"],
        request_hash,
    )
    actual = (
        row["principal_type"],
        row["principal_id"],
        row["authority_source"],
        row["authority_version"],
        row["request_hash"],
    )
    if actual != expected:
        raise OutcomeLedgerDataError("repair idempotency key has different authority")
    return {
        "outcome": "replayed",
        "command_id": row["command_id"],
        "decision_id": row["decision_id"],
        "decision_digest": row["decision_digest"],
        "projection_version": int(row["resulting_projection_version"]),
        "original_outcome": row["outcome"],
    }


def _append_repair_audit_event(
    conn,
    *,
    command,
    request_hash,
    outcome,
    lifecycle,
    decision,
    prior_version,
    resulting_version,
    completed_at,
):
    sequence = int(
        conn.execute(
            "SELECT COALESCE(MAX(sequence), -1) + 1 FROM agent_events WHERE agent_run_id = ?",
            (command["workflow_id"],),
        ).fetchone()[0]
    )
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, action_id, sequence, event_type, status,
            principal_type, principal_id, note_text, is_policy_event,
            anchors_json, created_at
        ) VALUES (?, ?, NULL, ?, 'completion_projection_repaired', ?, ?, ?, ?, 1, ?, ?)
        """,
        (
            f"completion-projection-repair:{command['command_id']}",
            command["workflow_id"],
            sequence,
            outcome,
            command["principal_type"],
            command["principal_id"],
            f"Completion projection repair: {outcome}",
            canonical_json(
                {
                    "command_id": command["command_id"],
                    "idempotency_key": command["idempotency_key"],
                    "request_hash": request_hash,
                    "lifecycle_event_id": lifecycle["event_id"],
                    "decision_id": decision["decision_id"],
                    "decision_digest": decision["decision_digest"],
                    "authoritative_event_sequence": decision[
                        "authoritative_event_sequence"
                    ],
                    "prior_projection_version": prior_version,
                    "resulting_projection_version": resulting_version,
                }
            ),
            completed_at,
        ),
    )


def _last_repair(conn, tenant_id, workflow_id):
    row = conn.execute(
        """
        SELECT command_id, principal_id, outcome, decision_id, decision_digest,
               authoritative_event_sequence, resulting_projection_version,
               completed_at
        FROM workflow_completion_projection_repairs
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY completed_at DESC, command_id DESC LIMIT 1
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    return dict(row) if row is not None else None


def _validate_repair_command(command):
    required = (
        "command_id",
        "tenant_id",
        "workflow_id",
        "principal_type",
        "principal_id",
        "authority_source",
        "authority_version",
        "idempotency_key",
    )
    for field in required:
        value = command.get(field)
        if type(value) is not str or not value or value != value.strip():
            raise OutcomeLedgerDataError(f"{field} must be a canonical exact string")
    if command["principal_type"] != "human":
        raise OutcomeLedgerDataError("completion repair requires a human operator")
    if (
        command["authority_source"] != REPAIR_AUTHORITY_SOURCE
        or command["authority_version"] != REPAIR_AUTHORITY_VERSION
    ):
        raise OutcomeLedgerDataError("completion repair authority is not trusted")


def _repair_request_hash(tenant_id, workflow_id):
    return hashlib.sha256(
        canonical_json(
            {
                "operation": "repair_completion_projection",
                "tenant_id": tenant_id,
                "workflow_id": workflow_id,
            }
        ).encode("utf-8")
    ).hexdigest()


def _format_utc(value):
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


__all__ = [
    "REPAIR_AUTHORITY_SOURCE",
    "REPAIR_AUTHORITY_VERSION",
    "REPAIR_SCOPE",
    "get_completion_operational_view",
    "repair_completion_projection",
]
