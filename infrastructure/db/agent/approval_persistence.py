"""Shared row mapping and locked persistence helpers for approval adapters."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from infrastructure.db.core.json import from_json, to_json


def approval_row(row: sqlite3.Row) -> Dict[str, Any]:
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


def command_row(row: sqlite3.Row) -> Dict[str, Any]:
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


def event_row(row: sqlite3.Row) -> Dict[str, Any]:
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


def effect_execution_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "execution_id": row["execution_id"],
        "tenant_id": row["tenant_id"],
        "workflow_id": row["workflow_id"],
        "action_id": row["action_id"],
        "approval_id": row["approval_id"],
        "approval_envelope_digest": row["approval_envelope_digest"],
        "authorization_source_digest": row["authorization_source_digest"],
        "effect_idempotency_key": row["effect_idempotency_key"],
        "status": row["status"],
        "receipt_id": row["receipt_id"],
        "outputs_hash": row["outputs_hash"],
        "error_code": row["error_code"],
        "started_at": row["started_at"],
        "completed_at": row["completed_at"],
        "updated_at": row["updated_at"],
    }


def runtime_scope_locked(
    conn: sqlite3.Connection,
    *,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
) -> tuple[Dict[str, Any], Dict[str, Any]] | None:
    row = conn.execute(
        """
        SELECT
            r.id AS run_id,
            r.client_id,
            r.principal_type AS run_principal_type,
            r.principal_id AS run_principal_id,
            r.allowed_capabilities_json,
            r.budgets_json,
            r.registry_version AS run_registry_version,
            r.registry_fingerprint AS run_registry_fingerprint,
            r.harness_id,
            r.policy_profile_id,
            r.active_graph_revision,
            a.id AS action_id,
            a.agent_run_id,
            a.status AS action_status,
            a.capability_name,
            a.capability_version,
            a.tool_id,
            a.tool_version,
            a.effect_class,
            a.inputs_json,
            a.inputs_hash,
            a.snapshot_version,
            a.hypothesis_id,
            a.variant_id,
            a.validation_job_id,
            a.rationale_text,
            a.confidence,
            a.registry_version AS action_registry_version,
            a.registry_fingerprint AS action_registry_fingerprint,
            a.dedupe_key,
            a.approval_id AS action_approval_id,
            a.approval_envelope_digest AS action_approval_envelope_digest
        FROM agent_actions a
        JOIN agent_runs r ON r.id = a.agent_run_id
        WHERE a.id = ? AND a.agent_run_id = ? AND r.client_id = ?
        """,
        (action_id, workflow_id, tenant_id),
    ).fetchone()
    if not row:
        return None
    run = {
        "id": row["run_id"],
        "client_id": row["client_id"],
        "principal_type": row["run_principal_type"],
        "principal_id": row["run_principal_id"],
        "allowed_capabilities": from_json(row["allowed_capabilities_json"], default=[]),
        "budgets": from_json(row["budgets_json"], default={}),
        "registry_version": row["run_registry_version"],
        "registry_fingerprint": row["run_registry_fingerprint"],
        "harness_id": row["harness_id"],
        "policy_profile_id": row["policy_profile_id"],
        "active_graph_revision": int(row["active_graph_revision"]),
    }
    action = {
        "id": row["action_id"],
        "agent_run_id": row["agent_run_id"],
        "status": row["action_status"],
        "capability_name": row["capability_name"],
        "capability_version": row["capability_version"],
        "tool_id": row["tool_id"],
        "tool_version": row["tool_version"],
        "effect_class": row["effect_class"],
        "inputs": from_json(row["inputs_json"], default={}),
        "inputs_hash": row["inputs_hash"],
        "snapshot_version": int(row["snapshot_version"])
        if row["snapshot_version"] is not None
        else None,
        "hypothesis_id": row["hypothesis_id"],
        "variant_id": row["variant_id"],
        "validation_job_id": row["validation_job_id"],
        "rationale": row["rationale_text"],
        "confidence": row["confidence"],
        "registry_version": row["action_registry_version"],
        "registry_fingerprint": row["action_registry_fingerprint"],
        "dedupe_key": row["dedupe_key"],
        "approval_id": row["action_approval_id"],
        "approval_envelope_digest": row["action_approval_envelope_digest"],
    }
    return run, action


def insert_agent_audit_event_locked(
    conn: sqlite3.Connection,
    *,
    workflow_id: str,
    action_id: str,
    event: Dict[str, Any],
) -> None:
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, action_id, sequence, event_type, status,
            capability_name, capability_version, principal_type,
            principal_id, tool_id, skill_id, effect_class, trace_id,
            note_text, is_policy_event, anchors_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            str(event.get("id") or uuid.uuid4()),
            workflow_id,
            action_id,
            int(event.get("sequence") or 0),
            event["event_type"],
            event["status"],
            event.get("capability_name"),
            event.get("capability_version"),
            event.get("principal_type"),
            event.get("principal_id"),
            event.get("tool_id"),
            event.get("skill_id"),
            event.get("effect_class"),
            event.get("trace_id"),
            event.get("note"),
            1 if event.get("is_policy_event") else 0,
            to_json(event.get("anchors") or {}) or to_json({}),
        ),
    )


def parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError("effect authorization timestamp must be timezone aware")
    return parsed.astimezone(timezone.utc)


__all__ = [
    "approval_row",
    "command_row",
    "effect_execution_row",
    "event_row",
    "insert_agent_audit_event_locked",
    "parse_timestamp",
    "runtime_scope_locked",
]
