"""Transactional append operations for workflow outcome artifacts."""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timezone
from typing import Any

from domain.workflow.outcome_authority import HostCompletionAuthority
from domain.workflow.outcome_authority_serialization import (
    completion_authority_snapshot_digest,
    completion_authority_snapshot_payload,
)
from domain.workflow.outcome_evaluation import evaluate_completion
from domain.workflow.outcome_serialization import (
    completion_criteria_digest,
    completion_criteria_payload,
    completion_decision_digest,
    completion_decision_payload,
    evidence_digest,
    evidence_payload,
    task_result_digest,
    task_result_payload,
)
from domain.workflow.outcomes import (
    AuthoritativeTaskDefinition,
    CompletionAuthoritySnapshot,
    CompletionCriteria,
    CompletionDecision,
    EvidenceRecord,
    ResultValidationStatus,
    TaskResult,
    evidence_set_digest,
)
from infrastructure.db.workflow.outcome_reads import (
    get_authority_snapshot_locked,
    get_completion_contract_locked,
    get_evidence_by_digest_locked,
    get_evidence_locked,
    get_task_result_by_digest_locked,
    list_accepted_task_results_locked,
)
from infrastructure.db.workflow.outcome_rows import canonical_json


_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


def append_evidence(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    evidence: EvidenceRecord,
    request_hash: str,
    host_authority: HostCompletionAuthority,
) -> dict[str, Any]:
    payload = evidence_payload(evidence)
    digest = evidence_digest(evidence)
    return _write(
        conn,
        command=command,
        request_hash=request_hash,
        request_payload={"evidence_digest": digest},
        artifact_type="evidence",
        artifact_id=evidence.evidence_id,
        artifact_digest=digest,
        artifact_tenant_id=evidence.tenant_id,
        artifact_workflow_id=evidence.workflow_id,
        artifact_time=payload["observation"]["recorded_at"],
        authority_check=lambda: _require_evidence_authority(
            command, evidence, host_authority
        ),
        operation=lambda: conn.execute(
            """
            INSERT INTO workflow_evidence_records (
                evidence_id, evidence_digest, tenant_id, workflow_id,
                graph_revision, task_id, attempt_id, action_id, payload_json,
                recorded_at, command_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence.evidence_id,
                digest,
                evidence.tenant_id,
                evidence.workflow_id,
                evidence.graph_revision,
                evidence.task_id,
                evidence.attempt_id,
                evidence.action_id,
                canonical_json(payload),
                payload["observation"]["recorded_at"],
                command["command_id"],
            ),
        ),
    )


def append_task_result(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    result: TaskResult,
    request_hash: str,
    host_authority: HostCompletionAuthority,
) -> dict[str, Any]:
    payload = task_result_payload(result)
    digest = task_result_digest(result)

    def operation() -> None:
        evidence_records = []
        for evidence_id in result.evidence_ids:
            record = get_evidence_locked(
                conn,
                tenant_id=result.tenant_id,
                workflow_id=result.workflow_id,
                evidence_id=evidence_id,
            )
            if record is None:
                raise _WriteConflict("task result evidence does not exist")
            evidence = record["evidence"]
            if (
                evidence.graph_revision,
                evidence.task_id,
                evidence.attempt_id,
            ) != (result.graph_revision, result.task_id, result.attempt_id):
                raise _WriteConflict(
                    "task result evidence does not belong to its exact attempt"
                )
            evidence_records.append(record)
        if result.evidence_digest != evidence_set_digest(
            tuple(item["evidence"] for item in evidence_records)
        ):
            raise _WriteConflict(
                "task result evidence digest does not match durable evidence"
            )
        for item in evidence_records:
            evidence = item["evidence"]
            if (
                evidence.observed_at is not None
                and evidence.observed_at > result.created_at
            ):
                raise _WriteConflict(
                    "task result cannot cite evidence observed after result creation"
                )
            if (
                result.validated_at is not None
                and evidence.recorded_at > result.validated_at
            ):
                raise _WriteConflict(
                    "task result cannot cite evidence recorded after result validation"
                )
        conn.execute(
            """
            INSERT INTO workflow_task_results (
                result_id, result_digest, tenant_id, workflow_id,
                graph_revision, task_id, attempt_id, assignment_id,
                validation_status, payload_json, created_at, validated_at,
                command_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result.result_id,
                digest,
                result.tenant_id,
                result.workflow_id,
                result.graph_revision,
                result.task_id,
                result.attempt_id,
                result.assignment_id,
                result.validation_status.value,
                canonical_json(payload),
                payload["created_at"],
                payload["validation"]["validated_at"],
                command["command_id"],
            ),
        )
        conn.executemany(
            """
            INSERT INTO workflow_result_evidence (
                result_id, evidence_id, evidence_digest
            ) VALUES (?, ?, ?)
            """,
            tuple(
                (
                    result.result_id,
                    item["evidence"].evidence_id,
                    item["evidence_digest"],
                )
                for item in evidence_records
            ),
        )

    return _write(
        conn,
        command=command,
        request_hash=request_hash,
        request_payload={"result_digest": digest},
        artifact_type="task_result",
        artifact_id=result.result_id,
        artifact_digest=digest,
        artifact_tenant_id=result.tenant_id,
        artifact_workflow_id=result.workflow_id,
        artifact_time=payload["validation"]["validated_at"] or payload["created_at"],
        authority_check=lambda: _require_result_authority(
            command, result, host_authority
        ),
        operation=operation,
    )


def publish_completion_contract(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    criteria: CompletionCriteria,
    task_definitions: tuple[AuthoritativeTaskDefinition, ...],
    request_hash: str,
    host_authority: HostCompletionAuthority,
) -> dict[str, Any]:
    payload = completion_criteria_payload(criteria)
    digest = completion_criteria_digest(criteria)
    definitions_hash = _definitions_digest(task_definitions)

    def operation() -> None:
        if (
            tuple(item.task_id for item in task_definitions)
            != criteria.required_task_ids
        ):
            raise _WriteConflict(
                "completion task definitions do not match required membership"
            )
        conn.execute(
            """
            INSERT INTO workflow_completion_criteria (
                criteria_digest, criteria_id, criteria_version, tenant_id,
                workflow_id, graph_revision, objective_id, authority_hash,
                payload_json, created_at, command_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                digest,
                criteria.criteria_id,
                criteria.criteria_version,
                criteria.tenant_id,
                criteria.workflow_id,
                criteria.graph_revision,
                criteria.objective_id,
                criteria.authority_hash,
                canonical_json(payload),
                payload["created_at"],
                command["command_id"],
            ),
        )
        conn.executemany(
            """
            INSERT INTO workflow_completion_task_definitions (
                criteria_digest, task_id, task_input_hash, result_schema_id,
                result_schema_version, result_schema_hash
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            tuple(
                (
                    digest,
                    item.task_id,
                    item.task_input_hash,
                    item.result_schema_id,
                    item.result_schema_version,
                    item.result_schema_hash,
                )
                for item in task_definitions
            ),
        )
        persisted = get_completion_contract_locked(
            conn,
            tenant_id=criteria.tenant_id,
            workflow_id=criteria.workflow_id,
            criteria_id=criteria.criteria_id,
            criteria_hash=digest,
        )
        if persisted is None or persisted["task_definitions"] != task_definitions:
            raise _WriteConflict("completion contract could not be reconstructed")

    return _write(
        conn,
        command=command,
        request_hash=request_hash,
        request_payload={
            "criteria_hash": digest,
            "task_definitions_hash": definitions_hash,
        },
        artifact_type="completion_contract",
        artifact_id=criteria.criteria_id,
        artifact_digest=digest,
        artifact_tenant_id=criteria.tenant_id,
        artifact_workflow_id=criteria.workflow_id,
        artifact_time=payload["created_at"],
        authority_check=lambda: _require_criteria_authority(
            command, criteria, host_authority
        ),
        operation=operation,
    )


def commit_authority_snapshot(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    snapshot_id: str,
    snapshot: CompletionAuthoritySnapshot,
    issued_at: str,
    request_hash: str,
    host_authority: HostCompletionAuthority,
) -> dict[str, Any]:
    payload = completion_authority_snapshot_payload(snapshot)
    digest = completion_authority_snapshot_digest(snapshot)

    def operation() -> None:
        publication = get_completion_contract_locked(
            conn,
            tenant_id=snapshot.tenant_id,
            workflow_id=snapshot.workflow_id,
            criteria_id=snapshot.criteria_id,
            criteria_hash=snapshot.criteria_hash,
        )
        if publication is None:
            raise _WriteConflict("snapshot completion contract does not exist")
        _require_not_before(issued_at, publication["criteria"].created_at)
        if (
            snapshot.task_definitions != publication["task_definitions"]
            or snapshot.criteria_authority_hash
            != publication["criteria"].authority_hash
            or snapshot.publishing_authority
            != publication["criteria"].publishing_authority
        ):
            raise _WriteConflict("snapshot does not match host completion contract")
        definitions_by_task = {item.task_id: item for item in snapshot.task_definitions}
        authoritative_results = [
            record
            for record in list_accepted_task_results_locked(
                conn,
                tenant_id=snapshot.tenant_id,
                workflow_id=snapshot.workflow_id,
                graph_revision=snapshot.graph_revision,
            )
            if record["result"].task_id in definitions_by_task
        ]
        authoritative_tasks = [
            record["result"].task_id for record in authoritative_results
        ]
        if len(authoritative_tasks) != len(set(authoritative_tasks)):
            raise _WriteConflict(
                "multiple accepted results make host authority ambiguous"
            )
        if {record["result_digest"] for record in authoritative_results} != {
            item.accepted_result_hash for item in snapshot.accepted_result_attestations
        }:
            raise _WriteConflict(
                "snapshot does not contain the authoritative accepted result set"
            )
        result_records = []
        for attestation in snapshot.accepted_result_attestations:
            record = get_task_result_by_digest_locked(
                conn,
                tenant_id=snapshot.tenant_id,
                workflow_id=snapshot.workflow_id,
                result_digest=attestation.accepted_result_hash,
            )
            if record is None:
                raise _WriteConflict("snapshot attested result does not exist")
            result = record["result"]
            if result.validated_at is None:
                raise _WriteConflict("snapshot accepted result lacks validation time")
            _require_not_before(issued_at, result.validated_at)
            if (
                result.validation_status is not ResultValidationStatus.ACCEPTED
                or result.task_id != attestation.task_id
                or result.attempt_id != attestation.attempt_id
                or result.assignment_id != attestation.assignment_id
                or result.validation_authority != attestation.validation_authority
            ):
                raise _WriteConflict(
                    "snapshot attestation does not match accepted durable result"
                )
            definition = definitions_by_task.get(result.task_id)
            if definition is None or (
                result.task_input_hash,
                result.result_schema_id,
                result.result_schema_version,
                result.result_schema_hash,
            ) != (
                definition.task_input_hash,
                definition.result_schema_id,
                definition.result_schema_version,
                definition.result_schema_hash,
            ):
                raise _WriteConflict(
                    "snapshot result does not match authoritative task definition"
                )
            result_records.append(record)
        conn.execute(
            """
            INSERT INTO workflow_completion_authority_snapshots (
                snapshot_id, snapshot_digest, tenant_id, workflow_id,
                graph_revision, objective_id, criteria_id, criteria_digest,
                payload_json, issued_at, command_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                digest,
                snapshot.tenant_id,
                snapshot.workflow_id,
                snapshot.graph_revision,
                snapshot.objective_id,
                snapshot.criteria_id,
                snapshot.criteria_hash,
                canonical_json(payload),
                issued_at,
                command["command_id"],
            ),
        )
        conn.executemany(
            """
            INSERT INTO workflow_completion_snapshot_results (
                snapshot_id, task_id, result_id, result_digest
            ) VALUES (?, ?, ?, ?)
            """,
            tuple(
                (
                    snapshot_id,
                    record["result"].task_id,
                    record["result"].result_id,
                    record["result_digest"],
                )
                for record in result_records
            ),
        )
        persisted = get_authority_snapshot_locked(
            conn,
            tenant_id=snapshot.tenant_id,
            workflow_id=snapshot.workflow_id,
            snapshot_id=snapshot_id,
        )
        if persisted is None or persisted["snapshot_digest"] != digest:
            raise _WriteConflict("authority snapshot could not be reconstructed")

    return _write(
        conn,
        command=command,
        request_hash=request_hash,
        request_payload={"snapshot_id": snapshot_id, "snapshot_digest": digest},
        artifact_type="authority_snapshot",
        artifact_id=snapshot_id,
        artifact_digest=digest,
        artifact_tenant_id=snapshot.tenant_id,
        artifact_workflow_id=snapshot.workflow_id,
        artifact_time=issued_at,
        authority_check=lambda: _require_snapshot_authority(
            command, snapshot, host_authority
        ),
        operation=operation,
    )


def commit_completion_decision(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    decision: CompletionDecision,
    snapshot_id: str,
    result_bindings: tuple[tuple[str, str], ...],
    evidence_bindings: tuple[tuple[str, str], ...],
    request_hash: str,
    host_authority: HostCompletionAuthority,
) -> dict[str, Any]:
    payload = completion_decision_payload(decision)
    digest = completion_decision_digest(decision)

    def operation() -> None:
        snapshot_record = get_authority_snapshot_locked(
            conn,
            tenant_id=decision.tenant_id,
            workflow_id=decision.workflow_id,
            snapshot_id=snapshot_id,
        )
        if snapshot_record is None:
            raise _WriteConflict("decision authority snapshot does not exist")
        _require_not_before(payload["evaluated_at"], snapshot_record["issued_at"])
        snapshot = snapshot_record["snapshot"]
        publication = get_completion_contract_locked(
            conn,
            tenant_id=decision.tenant_id,
            workflow_id=decision.workflow_id,
            criteria_id=snapshot.criteria_id,
            criteria_hash=snapshot.criteria_hash,
        )
        if publication is None:
            raise _WriteConflict("decision completion contract does not exist")
        results = _resolve_result_bindings(conn, decision, result_bindings)
        evidence = _resolve_evidence_bindings(conn, decision, evidence_bindings)
        expected_result_digests = tuple(
            item.accepted_result_hash for item in snapshot.accepted_result_attestations
        )
        if tuple(item["result_digest"] for item in results) != tuple(
            sorted(expected_result_digests)
        ):
            raise _WriteConflict(
                "decision results do not match authority snapshot attestations"
            )
        expected_evidence = {
            evidence_id
            for item in results
            for evidence_id in item["result"].evidence_ids
        }
        if {item["evidence"].evidence_id for item in evidence} != expected_evidence:
            raise _WriteConflict(
                "decision evidence does not match exact result evidence sets"
            )
        reproduced = evaluate_completion(
            decision_id=decision.decision_id,
            criteria=publication["criteria"],
            authority_snapshot=snapshot,
            results=tuple(item["result"] for item in results),
            evidence=tuple(item["evidence"] for item in evidence),
            evaluated_at=decision.evaluated_at,
            authoritative_event_sequence=decision.authoritative_event_sequence,
        )
        if completion_decision_digest(reproduced) != digest:
            raise _WriteConflict(
                "completion decision does not match deterministic evaluation"
            )
        conn.execute(
            """
            INSERT INTO workflow_completion_decisions (
                decision_id, decision_digest, tenant_id, workflow_id,
                graph_revision, objective_id, criteria_id, criteria_digest,
                snapshot_id, snapshot_digest, status,
                authoritative_event_sequence, payload_json, evaluated_at,
                command_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                decision.decision_id,
                digest,
                decision.tenant_id,
                decision.workflow_id,
                decision.graph_revision,
                decision.objective_id,
                decision.criteria_id,
                decision.criteria_hash,
                snapshot_id,
                snapshot_record["snapshot_digest"],
                decision.status.value,
                decision.authoritative_event_sequence,
                canonical_json(payload),
                payload["evaluated_at"],
                command["command_id"],
            ),
        )
        conn.executemany(
            """
            INSERT INTO workflow_completion_decision_results (
                decision_id, result_id, result_digest
            ) VALUES (?, ?, ?)
            """,
            tuple(
                (decision.decision_id, item["result"].result_id, item["result_digest"])
                for item in results
            ),
        )
        conn.executemany(
            """
            INSERT INTO workflow_completion_decision_evidence (
                decision_id, evidence_id, evidence_digest
            ) VALUES (?, ?, ?)
            """,
            tuple(
                (
                    decision.decision_id,
                    item["evidence"].evidence_id,
                    item["evidence_digest"],
                )
                for item in evidence
            ),
        )

    snapshot_record = get_authority_snapshot_locked(
        conn,
        tenant_id=decision.tenant_id,
        workflow_id=decision.workflow_id,
        snapshot_id=snapshot_id,
    )
    if snapshot_record is None:
        return {"outcome": "conflict", "reason": "authority snapshot is unavailable"}
    return _write(
        conn,
        command=command,
        request_hash=request_hash,
        request_payload={
            "snapshot_id": snapshot_id,
            "snapshot_digest": snapshot_record["snapshot_digest"],
            "decision_digest": digest,
        },
        artifact_type="completion_decision",
        artifact_id=decision.decision_id,
        artifact_digest=digest,
        artifact_tenant_id=decision.tenant_id,
        artifact_workflow_id=decision.workflow_id,
        artifact_time=payload["evaluated_at"],
        authority_check=lambda: _require_decision_authority(
            command, decision, host_authority
        ),
        operation=operation,
    )


class _WriteConflict(RuntimeError):
    pass


def _write(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    request_hash: str,
    request_payload: dict[str, object],
    artifact_type: str,
    artifact_id: str,
    artifact_digest: str,
    artifact_tenant_id: str,
    artifact_workflow_id: str,
    artifact_time: str,
    authority_check,
    operation,
) -> dict[str, Any]:
    expected_type = command.get("command_type")
    try:
        _validate_command(command)
        authority_check()
        _require_digest("request_hash", request_hash)
        _require_digest("artifact_digest", artifact_digest)
        _require_not_before(command["issued_at"], artifact_time)
        if (command["tenant_id"], command["workflow_id"]) != (
            artifact_tenant_id,
            artifact_workflow_id,
        ):
            raise _WriteConflict("command scope does not match artifact scope")
        if request_hash != _request_hash(expected_type, request_payload):
            raise _WriteConflict("command request hash does not match exact artifact")
        conn.execute("BEGIN IMMEDIATE")
        replay = _command_replay(
            conn,
            command=command,
            request_hash=request_hash,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            artifact_digest=artifact_digest,
        )
        if replay is not None:
            conn.commit()
            return replay
        if not conn.execute(
            "SELECT 1 FROM agent_runs WHERE client_id = ? AND id = ?",
            (command["tenant_id"], command["workflow_id"]),
        ).fetchone():
            raise _WriteConflict("command workflow is outside tenant scope")
        conn.execute(
            """
            INSERT INTO workflow_outcome_commands (
                command_id, tenant_id, workflow_id, command_type, principal_id,
                authority_source, authority_version, idempotency_key,
                request_hash, artifact_type, artifact_id, artifact_digest,
                issued_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                command["command_id"],
                command["tenant_id"],
                command["workflow_id"],
                command["command_type"],
                command["principal_id"],
                command["authority_source"],
                command["authority_version"],
                command["idempotency_key"],
                request_hash,
                artifact_type,
                artifact_id,
                artifact_digest,
                command["issued_at"],
                command["issued_at"],
            ),
        )
        operation()
        conn.commit()
        return {
            "outcome": "applied",
            "command_id": command["command_id"],
            "artifact_type": artifact_type,
            "artifact_id": artifact_id,
            "artifact_digest": artifact_digest,
        }
    except (_WriteConflict, sqlite3.IntegrityError, sqlite3.OperationalError) as exc:
        conn.rollback()
        return {"outcome": "conflict", "reason": str(exc)}


def _command_replay(
    conn: sqlite3.Connection,
    *,
    command: dict[str, Any],
    request_hash: str,
    artifact_type: str,
    artifact_id: str,
    artifact_digest: str,
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT * FROM workflow_outcome_commands
        WHERE tenant_id = ? AND workflow_id = ? AND idempotency_key = ?
        """,
        (
            command["tenant_id"],
            command["workflow_id"],
            command["idempotency_key"],
        ),
    ).fetchone()
    if row is None:
        return None
    expected = (
        command["command_type"],
        command["principal_id"],
        command["authority_source"],
        command["authority_version"],
        request_hash,
        artifact_type,
        artifact_id,
        artifact_digest,
    )
    actual = (
        row["command_type"],
        row["principal_id"],
        row["authority_source"],
        row["authority_version"],
        row["request_hash"],
        row["artifact_type"],
        row["artifact_id"],
        row["artifact_digest"],
    )
    if actual != expected:
        raise _WriteConflict("idempotency key was already used for another request")
    return {
        "outcome": "replayed",
        "command_id": row["command_id"],
        "artifact_type": row["artifact_type"],
        "artifact_id": row["artifact_id"],
        "artifact_digest": row["artifact_digest"],
    }


def _resolve_result_bindings(
    conn: sqlite3.Connection,
    decision: CompletionDecision,
    bindings: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    _validate_bindings("result_bindings", bindings)
    records = []
    for result_id, result_digest_value in bindings:
        record = get_task_result_by_digest_locked(
            conn,
            tenant_id=decision.tenant_id,
            workflow_id=decision.workflow_id,
            result_digest=result_digest_value,
        )
        if record is None or record["result"].result_id != result_id:
            raise _WriteConflict("decision result binding does not resolve exactly")
        if record["result"].graph_revision != decision.graph_revision:
            raise _WriteConflict("decision result revision is invalid")
        records.append(record)
    return sorted(records, key=lambda item: item["result_digest"])


def _resolve_evidence_bindings(
    conn: sqlite3.Connection,
    decision: CompletionDecision,
    bindings: tuple[tuple[str, str], ...],
) -> list[dict[str, Any]]:
    _validate_bindings("evidence_bindings", bindings)
    records = []
    for evidence_id, evidence_digest_value in bindings:
        record = get_evidence_by_digest_locked(
            conn,
            tenant_id=decision.tenant_id,
            workflow_id=decision.workflow_id,
            evidence_digest=evidence_digest_value,
        )
        if record is None or record["evidence"].evidence_id != evidence_id:
            raise _WriteConflict("decision evidence binding does not resolve exactly")
        if record["evidence"].graph_revision != decision.graph_revision:
            raise _WriteConflict("decision evidence revision is invalid")
        records.append(record)
    return sorted(records, key=lambda item: item["evidence"].evidence_id)


def _validate_bindings(name: str, bindings: object) -> None:
    if type(bindings) is not tuple:
        raise _WriteConflict(f"{name} must be an exact tuple")
    if any(
        type(item) is not tuple
        or len(item) != 2
        or any(type(value) is not str for value in item)
        for item in bindings
    ):
        raise _WriteConflict(f"{name} must contain exact identifier/digest pairs")
    if len(set(bindings)) != len(bindings) or tuple(sorted(bindings)) != bindings:
        raise _WriteConflict(f"{name} must be unique and canonical")


def _validate_command(command: object) -> None:
    if type(command) is not dict:
        raise _WriteConflict("command must be an exact object")
    expected = {
        "command_id",
        "tenant_id",
        "workflow_id",
        "command_type",
        "principal_id",
        "authority_source",
        "authority_version",
        "idempotency_key",
        "issued_at",
    }
    if set(command) != expected or any(type(key) is not str for key in command):
        raise _WriteConflict("command fields must match outcome ledger v1")
    for key, value in command.items():
        if type(value) is not str or not value or value != value.strip():
            raise _WriteConflict(f"command {key} must be a canonical exact string")
    _parse_utc(command["issued_at"])


def _require_evidence_authority(
    command: dict[str, Any],
    evidence: EvidenceRecord,
    host_authority: HostCompletionAuthority,
) -> None:
    _require_host_authority(host_authority)
    if command["principal_id"] != evidence.provenance.producer_principal_id:
        raise _WriteConflict("evidence command principal is not its producer")


def _require_result_authority(
    command: dict[str, Any],
    result: TaskResult,
    host_authority: HostCompletionAuthority,
) -> None:
    _require_host_authority(host_authority)
    if result.validation_status is ResultValidationStatus.PENDING:
        if command["principal_id"] != result.producer_principal_id:
            raise _WriteConflict("pending result command principal is not its producer")
        return
    if result.validation_authority != host_authority.result_validation_authority:
        raise _WriteConflict("result validation authority is not trusted by the host")
    _require_command_authority(
        command,
        host_authority.result_validation_authority.principal_id,
        host_authority.result_validation_authority.authority_source,
        host_authority.result_validation_authority.authority_version,
    )


def _require_criteria_authority(
    command: dict[str, Any],
    criteria: CompletionCriteria,
    host_authority: HostCompletionAuthority,
) -> None:
    _require_host_authority(host_authority)
    if (
        criteria.publishing_authority != host_authority.publishing_authority
        or criteria.authority_hash != host_authority.criteria_authority_hash
    ):
        raise _WriteConflict("completion criteria authority is not trusted by the host")
    authority = host_authority.publishing_authority
    _require_command_authority(
        command,
        authority.principal_id,
        authority.authority_source,
        authority.authority_version,
    )


def _require_snapshot_authority(
    command: dict[str, Any],
    snapshot: CompletionAuthoritySnapshot,
    host_authority: HostCompletionAuthority,
) -> None:
    _require_host_authority(host_authority)
    if (
        snapshot.publishing_authority != host_authority.publishing_authority
        or snapshot.criteria_authority_hash != host_authority.criteria_authority_hash
        or snapshot.evaluation_authority != host_authority.evaluation_authority
        or any(
            item.validation_authority != host_authority.result_validation_authority
            for item in snapshot.accepted_result_attestations
        )
    ):
        raise _WriteConflict("completion snapshot authority is not trusted by the host")
    authority = host_authority.evaluation_authority
    _require_command_authority(
        command,
        authority.principal_id,
        authority.authority_source,
        authority.authority_version,
    )


def _require_decision_authority(
    command: dict[str, Any],
    decision: CompletionDecision,
    host_authority: HostCompletionAuthority,
) -> None:
    _require_host_authority(host_authority)
    if decision.evaluation_authority != host_authority.evaluation_authority:
        raise _WriteConflict("completion decision authority is not trusted by the host")
    authority = host_authority.evaluation_authority
    _require_command_authority(
        command,
        authority.principal_id,
        authority.authority_source,
        authority.authority_version,
    )


def _require_host_authority(value: object) -> None:
    if type(value) is not HostCompletionAuthority:
        raise _WriteConflict("host outcome authority must be an exact trusted policy")


def _require_command_authority(
    command: dict[str, Any], principal_id: str, source: str, version: str
) -> None:
    if (
        command["principal_id"],
        command["authority_source"],
        command["authority_version"],
    ) != (principal_id, source, version):
        raise _WriteConflict("command authority is not trusted for this artifact")


def _require_not_before(value: str, lower_bound: str | datetime) -> None:
    actual = _parse_utc(value)
    minimum = _parse_utc(lower_bound) if type(lower_bound) is str else lower_bound
    if type(minimum) is not datetime or type(minimum.tzinfo) is not timezone:
        raise _WriteConflict("artifact timestamp must use immutable UTC timezone")
    if actual < minimum:
        raise _WriteConflict("command or artifact timestamp precedes its dependency")


def _parse_utc(value: object) -> datetime:
    if type(value) is not str:
        raise _WriteConflict("command timestamp must be canonical UTC text")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _WriteConflict("command timestamp must be canonical UTC text") from exc
    if type(parsed.tzinfo) is not timezone:
        raise _WriteConflict("command timestamp must use immutable UTC timezone")
    canonical = parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    canonical = canonical.replace("+00:00", "Z")
    if canonical != value:
        raise _WriteConflict("command timestamp must be canonical UTC text")
    return parsed


def _definitions_digest(
    definitions: tuple[AuthoritativeTaskDefinition, ...],
) -> str:
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


def _request_hash(command_type: object, payload: dict[str, object]) -> str:
    return _json_digest({"command_type": command_type, "request": payload})


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_digest(field_name: str, value: object) -> None:
    if type(value) is not str or _DIGEST_PATTERN.fullmatch(value) is None:
        raise _WriteConflict(f"{field_name} must be a lowercase SHA-256 digest")


__all__ = [
    "append_evidence",
    "append_task_result",
    "commit_authority_snapshot",
    "commit_completion_decision",
    "publish_completion_contract",
]
