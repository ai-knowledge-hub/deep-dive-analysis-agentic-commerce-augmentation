"""Independent validators for governed semantic compatibility sources."""

from __future__ import annotations

import json
import sqlite3
from typing import Any

from domain.workflow.approval_execution import approval_effect_start_snapshot_digest
from domain.workflow.approval_serialization import (
    approval_envelope_digest,
    approval_envelope_from_payload,
)
from infrastructure.db.core.json import from_json
import infrastructure.db.workflow.outcome_reads as outcome_reads


def validate_authoritative_semantic_bundles_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> None:
    """Fail closed unless every projected ledger reconstructs independently."""

    _validate_approval_bundles_locked(
        conn, tenant_id=tenant_id, workflow_id=workflow_id
    )
    _validate_effect_bundles_locked(conn, tenant_id=tenant_id, workflow_id=workflow_id)
    lifecycle = conn.execute(
        """
        SELECT * FROM workflow_completion_lifecycle_events
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY authoritative_event_sequence ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    cursor = conn.execute(
        """
        SELECT current_sequence FROM workflow_completion_event_cursors
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (tenant_id, workflow_id),
    ).fetchone()
    if cursor is None:
        if lifecycle:
            raise ValueError("completion lifecycle cursor is unavailable")
    else:
        expected_sequences = list(range(int(cursor["current_sequence"]) + 1))
        actual_sequences = [
            int(event["authoritative_event_sequence"]) for event in lifecycle
        ]
        if actual_sequences != expected_sequences:
            raise ValueError("completion lifecycle history is incomplete")
    lifecycle_decision_ids: set[str] = set()
    for event in lifecycle:
        lifecycle_decision_ids.add(str(event["decision_id"]))
        decision = conn.execute(
            """
            SELECT * FROM workflow_completion_decisions
            WHERE decision_id = ? AND tenant_id = ? AND workflow_id = ?
            """,
            (event["decision_id"], tenant_id, workflow_id),
        ).fetchone()
        command = conn.execute(
            """
            SELECT * FROM workflow_outcome_commands
            WHERE command_id = ? AND tenant_id = ? AND workflow_id = ?
            """,
            (event["command_id"], tenant_id, workflow_id),
        ).fetchone()
        if (
            decision is None
            or command is None
            or not (
                decision["decision_digest"] == event["decision_digest"]
                and int(decision["graph_revision"]) == int(event["graph_revision"])
                and decision["status"] == event["completion_status"]
                and int(decision["authoritative_event_sequence"])
                == int(event["authoritative_event_sequence"])
                and decision["command_id"] == event["command_id"]
                and command["command_type"] == "record_completion_decision"
                and command["artifact_type"] == "completion_decision"
                and command["artifact_id"] == event["decision_id"]
                and command["artifact_digest"] == event["decision_digest"]
            )
        ):
            raise ValueError("completion lifecycle decision bundle is invalid")
    decisions = conn.execute(
        """
        SELECT decision_id
        FROM workflow_completion_decisions
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY decision_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    if {str(row["decision_id"]) for row in decisions} != lifecycle_decision_ids:
        raise ValueError("completion decision history disagrees with its lifecycle")
    for row in decisions:
        bundle = outcome_reads.load_evaluation_bundle_locked(
            conn,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            decision_id=row["decision_id"],
        )
        if bundle is None:
            raise outcome_reads.OutcomeLedgerDataError(
                "completion decision bundle is unavailable"
            )


def _validate_approval_bundles_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> None:
    action_anchors = conn.execute(
        """
        SELECT approval_id, approval_envelope_digest
        FROM agent_actions
        WHERE agent_run_id = ? AND approval_id IS NOT NULL
        ORDER BY id ASC
        """,
        (workflow_id,),
    ).fetchall()
    effect_anchors = conn.execute(
        """
        SELECT approval_id
        FROM approval_effect_executions
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY execution_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    records = conn.execute(
        """
        SELECT * FROM approval_records
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY approval_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    records_by_id = {str(record["approval_id"]): record for record in records}
    expected_approval_ids = {
        str(anchor["approval_id"]) for anchor in (*action_anchors, *effect_anchors)
    }
    if not expected_approval_ids.issubset(records_by_id):
        raise ValueError("governed action approval history is unavailable")
    for anchor in action_anchors:
        record = records_by_id[str(anchor["approval_id"])]
        if (
            type(anchor["approval_envelope_digest"]) is not str
            or anchor["approval_envelope_digest"] != record["envelope_digest"]
        ):
            raise ValueError("governed action approval projection is inconsistent")
    for record in records:
        envelope = _approval_envelope(record["envelope_json"], "approval record")
        events = conn.execute(
            """
            SELECT event.*, command.first_event_sequence,
                   command.last_event_sequence,
                   command.tenant_id AS command_tenant_id,
                   command.workflow_id AS command_workflow_id,
                   command.action_id AS command_action_id,
                   command.approval_id AS command_approval_id,
                   command.principal_type AS command_principal_type,
                   command.principal_id AS command_principal_id,
                   command.authority_source AS command_authority_source,
                   command.authority_version AS command_authority_version
            FROM approval_events event
            JOIN approval_commands command ON command.command_id = event.command_id
            WHERE event.tenant_id = ? AND event.workflow_id = ?
              AND event.approval_id = ?
            ORDER BY event.sequence ASC
            """,
            (tenant_id, workflow_id, record["approval_id"]),
        ).fetchall()
        expected_sequences = list(range(1, int(record["current_sequence"]) + 1))
        if [int(event["sequence"]) for event in events] != expected_sequences:
            raise ValueError("approval history is incomplete")
        for event in events:
            event_envelope = _approval_envelope(
                event["envelope_json"], "approval event"
            )
            binding = event_envelope.binding
            if not (
                approval_envelope_digest(event_envelope) == event["envelope_digest"]
                and binding.tenant_id == tenant_id
                and binding.workflow_id == workflow_id
                and binding.action_id == event["action_id"]
                and binding.approval_id == event["approval_id"]
                and event_envelope.status.value == event["status"]
                and int(event["first_event_sequence"])
                <= int(event["sequence"])
                <= int(event["last_event_sequence"])
                and event["command_tenant_id"] == tenant_id
                and event["command_workflow_id"] == workflow_id
                and event["command_action_id"] == event["action_id"]
                and event["command_approval_id"] == event["approval_id"]
                and event["command_principal_type"] == event["principal_type"]
                and event["command_principal_id"] == event["principal_id"]
                and event["command_authority_source"] == event["authority_source"]
                and event["command_authority_version"] == event["authority_version"]
            ):
                raise ValueError("approval event history is not canonical")
        if not events:
            raise ValueError("approval projection has no append-only history")
        tail = events[-1]
        if not (
            approval_envelope_digest(envelope) == record["envelope_digest"]
            and envelope.binding.tenant_id == tenant_id
            and envelope.binding.workflow_id == workflow_id
            and envelope.binding.action_id == record["action_id"]
            and envelope.binding.approval_id == record["approval_id"]
            and envelope.status.value == record["current_status"]
            and tail["envelope_digest"] == record["envelope_digest"]
            and tail["status"] == record["current_status"]
            and _approval_envelope(tail["envelope_json"], "approval tail") == envelope
        ):
            raise ValueError("approval projection diverges from append-only history")


def _approval_envelope(raw: object, source: str):
    if type(raw) is not str:
        raise ValueError(f"{source} envelope is not canonical text")
    try:
        payload = json.loads(raw)
        if type(payload) is not dict:
            raise TypeError("approval envelope must be an object")
        return approval_envelope_from_payload(payload)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"{source} envelope is invalid") from exc


def _validate_effect_bundles_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str
) -> None:
    action_anchors = conn.execute(
        """
        SELECT id AS action_id, approval_id, receipt_id, outputs_hash
        FROM agent_actions
        WHERE agent_run_id = ? AND approval_id IS NOT NULL
          AND receipt_id IS NOT NULL
        ORDER BY id ASC
        """,
        (workflow_id,),
    ).fetchall()
    fulfilled_anchors = conn.execute(
        """
        SELECT approval_id, action_id, envelope_json
        FROM approval_records
        WHERE tenant_id = ? AND workflow_id = ? AND current_status = 'fulfilled'
        ORDER BY approval_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    effects = conn.execute(
        """
        SELECT * FROM approval_effect_executions
        WHERE tenant_id = ? AND workflow_id = ? AND status = 'succeeded'
        ORDER BY execution_id ASC
        """,
        (tenant_id, workflow_id),
    ).fetchall()
    effects_by_approval = {str(effect["approval_id"]): effect for effect in effects}
    for anchor in action_anchors:
        effect = effects_by_approval.get(str(anchor["approval_id"]))
        if effect is None or not (
            effect["action_id"] == anchor["action_id"]
            and effect["receipt_id"] == anchor["receipt_id"]
            and effect["outputs_hash"] == anchor["outputs_hash"]
        ):
            raise ValueError("governed action effect bundle is unavailable")
    for anchor in fulfilled_anchors:
        envelope = _approval_envelope(anchor["envelope_json"], "fulfilled approval")
        effect = effects_by_approval.get(str(anchor["approval_id"]))
        if effect is None or not (
            effect["action_id"] == anchor["action_id"]
            and effect["receipt_id"] == envelope.fulfillment_receipt_id
        ):
            raise ValueError("fulfilled approval effect bundle is unavailable")
    for effect in effects:
        snapshot = from_json(effect["authorization_snapshot_json"], default=None)
        if type(snapshot) is not dict:
            raise ValueError("effect authorization snapshot is unavailable")
        envelope_payload = snapshot.get("approval_envelope")
        if type(envelope_payload) is not dict:
            raise ValueError("effect approval envelope is unavailable")
        envelope = approval_envelope_from_payload(envelope_payload)
        binding = envelope.binding
        if not (
            approval_effect_start_snapshot_digest(snapshot)
            == effect["authorization_snapshot_digest"]
            and approval_envelope_digest(envelope) == effect["approval_envelope_digest"]
            and snapshot.get("contract") == "workflow.approval-effect-start"
            and snapshot.get("version") == "1.0"
            and type(snapshot.get("executable_inputs")) is dict
            and type(snapshot.get("capability_contract")) is dict
            and type(snapshot.get("audit_context")) is dict
            and snapshot.get("authorization_source_digest")
            == effect["authorization_source_digest"]
            and binding.tenant_id == tenant_id
            and binding.workflow_id == workflow_id
            and binding.action_id == effect["action_id"]
            and binding.approval_id == effect["approval_id"]
            and binding.effect_idempotency_key == effect["effect_idempotency_key"]
        ):
            raise ValueError("effect start does not match its immutable authority")
        approved_event = conn.execute(
            """
            SELECT 1 FROM approval_events
            WHERE tenant_id = ? AND workflow_id = ? AND approval_id = ?
              AND action_id = ? AND envelope_digest = ?
            """,
            (
                tenant_id,
                workflow_id,
                effect["approval_id"],
                effect["action_id"],
                effect["approval_envelope_digest"],
            ),
        ).fetchone()
        if approved_event is None:
            raise ValueError("effect start has no exact approval event")
        _validate_effect_receipt_locked(conn, effect=effect, snapshot=snapshot)


def _validate_effect_receipt_locked(
    conn: sqlite3.Connection, *, effect: sqlite3.Row, snapshot: dict[str, Any]
) -> None:
    receipt_id = effect["receipt_id"]
    if type(receipt_id) is not str:
        raise ValueError("successful effect has no durable receipt")
    if receipt_id.startswith("validation-job:"):
        job_id = receipt_id.removeprefix("validation-job:")
        job = conn.execute(
            "SELECT * FROM validation_jobs WHERE id = ?", (job_id,)
        ).fetchone()
        inputs = snapshot["executable_inputs"]
        if job is None or not (
            job["client_id"] == effect["tenant_id"]
            and job["agent_action_id"] == effect["action_id"]
            and job["approval_id"] == effect["approval_id"]
            and job["effect_idempotency_key"] == effect["effect_idempotency_key"]
            and job["approval_effect_execution_id"] == effect["execution_id"]
            and job["entity_type"] == "experiment_run"
            and job["entity_id"] == inputs.get("experiment_id")
            and job["provider"] == inputs.get("provider")
            and job["mode"] == inputs.get("mode")
            and job["requested_model"] == inputs.get("model")
            and job["prompt_version"] == inputs.get("prompt_version")
        ):
            raise ValueError("validation receipt provenance is incomplete")
        if inputs.get("auto_run") is True:
            result = conn.execute(
                """
                SELECT 1 FROM validation_results
                WHERE job_id = ? AND provider = ? AND model IS ?
                """,
                (job_id, job["provider"], job["model"]),
            ).fetchone()
            if job["status"] != "completed" or result is None:
                raise ValueError("completed validation receipt result is unavailable")
        return
    if receipt_id == f"lab-promotion:{effect['execution_id']}":
        receipt = conn.execute(
            """
            SELECT * FROM governed_effect_receipts
            WHERE receipt_id = ? AND tenant_id = ?
            """,
            (receipt_id, effect["tenant_id"]),
        ).fetchone()
        if receipt is None or not (
            receipt["workflow_id"] == effect["workflow_id"]
            and receipt["action_id"] == effect["action_id"]
            and receipt["approval_id"] == effect["approval_id"]
            and receipt["effect_idempotency_key"] == effect["effect_idempotency_key"]
            and receipt["approval_effect_execution_id"] == effect["execution_id"]
            and receipt["outputs_hash"] == effect["outputs_hash"]
            and receipt["scope_status"] == "validated"
        ):
            raise ValueError("governed effect receipt provenance is incomplete")
        return
    raise ValueError("successful effect receipt type is unsupported")


__all__ = ["validate_authoritative_semantic_bundles_locked"]
