"""Strict row reconstruction for persisted workflow outcome artifacts."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from typing import Any

from domain.workflow.outcome_authority_serialization import (
    completion_authority_snapshot_digest,
    completion_authority_snapshot_from_payload,
)
from domain.workflow.outcome_serialization import (
    completion_criteria_digest,
    completion_criteria_from_payload,
    completion_decision_digest,
    completion_decision_from_payload,
    evidence_digest,
    evidence_from_payload,
    task_result_digest,
    task_result_from_payload,
)
from domain.workflow.outcomes import AuthoritativeTaskDefinition, OutcomeContractError


class OutcomeLedgerDataError(RuntimeError):
    """Raised when durable outcome data cannot reproduce its claimed artifact."""


def evidence_record(row: sqlite3.Row) -> dict[str, Any]:
    value = _parse("evidence", row["payload_json"], evidence_from_payload)
    digest = evidence_digest(value)
    _equal("evidence identity", value.evidence_id, row["evidence_id"])
    _equal("evidence digest", digest, row["evidence_digest"])
    _scope(row, value)
    _equal("evidence task", value.task_id, row["task_id"])
    _equal("evidence attempt", value.attempt_id, row["attempt_id"])
    _equal("evidence action", value.action_id, row["action_id"])
    _equal("evidence recorded_at", value.recorded_at, _timestamp(row["recorded_at"]))
    return {
        "evidence": value,
        "evidence_digest": digest,
        "command_id": row["command_id"],
    }


def task_result_record(row: sqlite3.Row) -> dict[str, Any]:
    value = _parse("task result", row["payload_json"], task_result_from_payload)
    digest = task_result_digest(value)
    _equal("result identity", value.result_id, row["result_id"])
    _equal("result digest", digest, row["result_digest"])
    _scope(row, value)
    _equal("result task", value.task_id, row["task_id"])
    _equal("result attempt", value.attempt_id, row["attempt_id"])
    _equal("result assignment", value.assignment_id, row["assignment_id"])
    _equal(
        "result validation status",
        value.validation_status.value,
        row["validation_status"],
    )
    _equal("result created_at", value.created_at, _timestamp(row["created_at"]))
    stored_validated_at = (
        None if row["validated_at"] is None else _timestamp(row["validated_at"])
    )
    _equal("result validated_at", value.validated_at, stored_validated_at)
    return {
        "result": value,
        "result_digest": digest,
        "command_id": row["command_id"],
    }


def criteria_record(
    row: sqlite3.Row, definition_rows: list[sqlite3.Row]
) -> dict[str, Any]:
    value = _parse(
        "completion criteria", row["payload_json"], completion_criteria_from_payload
    )
    digest = completion_criteria_digest(value)
    _equal("criteria identity", value.criteria_id, row["criteria_id"])
    _equal("criteria digest", digest, row["criteria_digest"])
    _scope(row, value)
    _equal("criteria version", value.criteria_version, row["criteria_version"])
    _equal("criteria objective", value.objective_id, row["objective_id"])
    _equal("criteria authority", value.authority_hash, row["authority_hash"])
    _equal("criteria created_at", value.created_at, _timestamp(row["created_at"]))
    definitions = tuple(
        AuthoritativeTaskDefinition(
            task_id=item["task_id"],
            task_input_hash=item["task_input_hash"],
            result_schema_id=item["result_schema_id"],
            result_schema_version=item["result_schema_version"],
            result_schema_hash=item["result_schema_hash"],
        )
        for item in definition_rows
    )
    if tuple(item.task_id for item in definitions) != value.required_task_ids:
        raise OutcomeLedgerDataError(
            "persisted task definitions do not match required task membership"
        )
    return {
        "criteria": value,
        "criteria_digest": digest,
        "task_definitions": definitions,
        "command_id": row["command_id"],
    }


def authority_snapshot_record(
    row: sqlite3.Row,
    *,
    publication: dict[str, Any],
    result_rows: list[sqlite3.Row],
) -> dict[str, Any]:
    value = _parse(
        "completion authority snapshot",
        row["payload_json"],
        completion_authority_snapshot_from_payload,
    )
    digest = completion_authority_snapshot_digest(value)
    _equal("snapshot digest", digest, row["snapshot_digest"])
    _scope(row, value)
    _equal("snapshot objective", value.objective_id, row["objective_id"])
    _equal("snapshot criteria identity", value.criteria_id, row["criteria_id"])
    _equal("snapshot criteria digest", value.criteria_hash, row["criteria_digest"])
    if (
        value.criteria_hash != publication["criteria_digest"]
        or value.criteria_id != publication["criteria"].criteria_id
        or value.task_definitions != publication["task_definitions"]
    ):
        raise OutcomeLedgerDataError(
            "persisted snapshot does not match its host completion contract"
        )
    bindings = {(item["task_id"], item["result_digest"]) for item in result_rows}
    attestations = {
        (item.task_id, item.accepted_result_hash)
        for item in value.accepted_result_attestations
    }
    if bindings != attestations:
        raise OutcomeLedgerDataError(
            "persisted snapshot result bindings do not match its authority payload"
        )
    return {
        "snapshot_id": row["snapshot_id"],
        "snapshot": value,
        "snapshot_digest": digest,
        "issued_at": _timestamp(row["issued_at"]),
        "command_id": row["command_id"],
    }


def decision_record(row: sqlite3.Row) -> dict[str, Any]:
    value = _parse(
        "completion decision", row["payload_json"], completion_decision_from_payload
    )
    digest = completion_decision_digest(value)
    _equal("decision identity", value.decision_id, row["decision_id"])
    _equal("decision digest", digest, row["decision_digest"])
    _scope(row, value)
    _equal("decision objective", value.objective_id, row["objective_id"])
    _equal("decision criteria identity", value.criteria_id, row["criteria_id"])
    _equal("decision criteria digest", value.criteria_hash, row["criteria_digest"])
    _equal("decision status", value.status.value, row["status"])
    _equal(
        "decision event sequence",
        value.authoritative_event_sequence,
        int(row["authoritative_event_sequence"]),
    )
    _equal("decision evaluated_at", value.evaluated_at, _timestamp(row["evaluated_at"]))
    return {
        "decision": value,
        "decision_digest": digest,
        "snapshot_id": row["snapshot_id"],
        "snapshot_digest": row["snapshot_digest"],
        "command_id": row["command_id"],
    }


def canonical_json(value: dict[str, Any]) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _parse(name: str, raw: object, parser):
    if type(raw) is not str:
        raise OutcomeLedgerDataError(f"persisted {name} payload is not text")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OutcomeLedgerDataError(
            f"persisted {name} payload is invalid JSON"
        ) from exc
    if type(value) is not dict:
        raise OutcomeLedgerDataError(f"persisted {name} payload is not an object")
    try:
        return parser(value)
    except (OutcomeContractError, TypeError, ValueError) as exc:
        raise OutcomeLedgerDataError(f"persisted {name} payload is invalid") from exc


def _scope(row: sqlite3.Row, value: object) -> None:
    actual = (
        getattr(value, "tenant_id"),
        getattr(value, "workflow_id"),
        getattr(value, "graph_revision"),
    )
    expected = (row["tenant_id"], row["workflow_id"], int(row["graph_revision"]))
    if actual != expected:
        raise OutcomeLedgerDataError("persisted artifact scope columns do not match")


def _equal(name: str, actual: object, expected: object) -> None:
    if actual != expected:
        raise OutcomeLedgerDataError(f"persisted {name} does not match")


def _timestamp(value: object) -> datetime:
    if type(value) is not str:
        raise OutcomeLedgerDataError("persisted timestamp is invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeLedgerDataError("persisted timestamp is invalid") from exc
    canonical = parsed.isoformat(timespec="microseconds").replace("+00:00", "Z")
    if parsed.utcoffset() is None or canonical != value:
        raise OutcomeLedgerDataError("persisted timestamp is not canonical UTC")
    return parsed


__all__ = [
    "OutcomeLedgerDataError",
    "authority_snapshot_record",
    "canonical_json",
    "criteria_record",
    "decision_record",
    "evidence_record",
    "task_result_record",
]
