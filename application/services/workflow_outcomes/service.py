"""Host-owned issuance and evaluation over the durable outcome ledger."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from application.ports.workflow_outcomes import WorkflowOutcomeLedgerStore
from application.services.workflow_outcomes.contracts import (
    HostCompletionAuthority,
    OutcomeLedgerCommand,
    OutcomeLedgerConflict,
)
from domain.workflow.outcome_authority_serialization import (
    completion_authority_snapshot_digest,
)
from domain.workflow.outcome_evaluation import evaluate_completion
from domain.workflow.outcome_serialization import (
    completion_criteria_digest,
    completion_decision_digest,
    evidence_digest,
    task_result_digest,
)
from domain.workflow.outcomes import (
    AcceptedTaskResultAttestation,
    AuthoritativeTaskDefinition,
    CompletionAuthoritySnapshot,
    CompletionCriteria,
    CompletionDecision,
    EvidenceRecord,
    OutcomeContractError,
    ResultValidationStatus,
    TaskResult,
)


class WorkflowOutcomeService:
    """Persist exact artifacts without granting them broader runtime authority."""

    def __init__(
        self,
        *,
        store: WorkflowOutcomeLedgerStore,
        host_authority: HostCompletionAuthority,
    ) -> None:
        self._store = store
        self._host_authority = host_authority

    def record_evidence(
        self, *, command: OutcomeLedgerCommand, evidence: EvidenceRecord
    ) -> dict[str, Any]:
        _require_scope(command, evidence.tenant_id, evidence.workflow_id)
        _require_not_before(
            "command issued_at", command.issued_at, evidence.recorded_at
        )
        _require_command_authority(
            command,
            principal_id=evidence.provenance.producer_principal_id,
            authority_source=command.authority_source,
            authority_version=command.authority_version,
        )
        digest = evidence_digest(evidence)
        return self._write(
            self._store.append_evidence,
            command=command,
            command_type="record_evidence",
            request_payload={"evidence_digest": digest},
            evidence=evidence,
        )

    def record_task_result(
        self, *, command: OutcomeLedgerCommand, result: TaskResult
    ) -> dict[str, Any]:
        _require_scope(command, result.tenant_id, result.workflow_id)
        _require_not_before("command issued_at", command.issued_at, result.created_at)
        if result.validated_at is not None:
            _require_not_before(
                "command issued_at", command.issued_at, result.validated_at
            )
        if result.validation_status is ResultValidationStatus.PENDING:
            _require_command_authority(
                command,
                principal_id=result.producer_principal_id,
                authority_source=command.authority_source,
                authority_version=command.authority_version,
            )
        else:
            authority = self._host_authority.result_validation_authority
            if result.validation_authority != authority:
                raise OutcomeContractError(
                    "validated result must match configured coordinator authority"
                )
            _require_command_authority(
                command,
                principal_id=authority.principal_id,
                authority_source=authority.authority_source,
                authority_version=authority.authority_version,
            )
        digest = task_result_digest(result)
        return self._write(
            self._store.append_task_result,
            command=command,
            command_type="record_task_result",
            request_payload={"result_digest": digest},
            result=result,
        )

    def publish_completion_contract(
        self,
        *,
        command: OutcomeLedgerCommand,
        criteria: CompletionCriteria,
        task_definitions: tuple[AuthoritativeTaskDefinition, ...],
    ) -> dict[str, Any]:
        _require_scope(command, criteria.tenant_id, criteria.workflow_id)
        _require_not_before("command issued_at", command.issued_at, criteria.created_at)
        if criteria.publishing_authority != self._host_authority.publishing_authority:
            raise OutcomeContractError(
                "criteria publishing authority must match configured host authority"
            )
        if criteria.authority_hash != self._host_authority.criteria_authority_hash:
            raise OutcomeContractError(
                "criteria authority hash must match configured host authority"
            )
        _require_command_authority(
            command,
            principal_id=criteria.publishing_authority.principal_id,
            authority_source=criteria.publishing_authority.authority_source,
            authority_version=criteria.publishing_authority.authority_version,
        )
        _validate_task_definitions(criteria, task_definitions)
        criteria_hash = completion_criteria_digest(criteria)
        definitions_hash = _definitions_digest(task_definitions)
        return self._write(
            self._store.publish_completion_contract,
            command=command,
            command_type="publish_completion_contract",
            request_payload={
                "criteria_hash": criteria_hash,
                "task_definitions_hash": definitions_hash,
            },
            criteria=criteria,
            task_definitions=task_definitions,
        )

    def issue_authority_snapshot(
        self,
        *,
        command: OutcomeLedgerCommand,
        snapshot_id: str,
        criteria_id: str,
        criteria_hash: str,
    ) -> dict[str, Any]:
        _require_identifier("snapshot_id", snapshot_id)
        _require_command_authority(
            command,
            principal_id=self._host_authority.evaluation_authority.principal_id,
            authority_source=self._host_authority.evaluation_authority.authority_source,
            authority_version=self._host_authority.evaluation_authority.authority_version,
        )
        publication = self._store.get_completion_contract(
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            criteria_id=criteria_id,
            criteria_hash=criteria_hash,
        )
        if publication is None:
            raise OutcomeLedgerConflict("completion contract does not exist")
        criteria = publication["criteria"]
        definitions = publication["task_definitions"]
        if (
            criteria.publishing_authority != self._host_authority.publishing_authority
            or criteria.authority_hash != self._host_authority.criteria_authority_hash
        ):
            raise OutcomeLedgerConflict(
                "persisted completion contract no longer matches host authority"
            )
        attestations = self._accepted_result_attestations(
            command=command,
            criteria=criteria,
            definitions=definitions,
        )
        snapshot = CompletionAuthoritySnapshot(
            tenant_id=criteria.tenant_id,
            workflow_id=criteria.workflow_id,
            graph_revision=criteria.graph_revision,
            objective_id=criteria.objective_id,
            criteria_id=criteria.criteria_id,
            criteria_hash=publication["criteria_digest"],
            criteria_authority_hash=criteria.authority_hash,
            publishing_authority=criteria.publishing_authority,
            evaluation_authority=self._host_authority.evaluation_authority,
            task_definitions=definitions,
            accepted_result_attestations=attestations,
        )
        _require_not_before(
            "snapshot issued_at", command.issued_at, criteria.created_at
        )
        accepted_records = self._store.list_accepted_task_results(
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            graph_revision=criteria.graph_revision,
        )
        for result_record in accepted_records:
            if result_record["result"].task_id not in criteria.required_task_ids:
                continue
            validated_at = result_record["result"].validated_at
            if validated_at is None:
                raise OutcomeLedgerConflict("accepted result lacks validation time")
            _require_not_before("snapshot issued_at", command.issued_at, validated_at)
        snapshot_hash = completion_authority_snapshot_digest(snapshot)
        return self._write(
            self._store.commit_authority_snapshot,
            command=command,
            command_type="issue_authority_snapshot",
            request_payload={
                "snapshot_id": snapshot_id,
                "snapshot_digest": snapshot_hash,
            },
            snapshot_id=snapshot_id,
            snapshot=snapshot,
            issued_at=_format_utc(command.issued_at),
        )

    def evaluate_and_record(
        self,
        *,
        command: OutcomeLedgerCommand,
        snapshot_id: str,
        decision_id: str,
        evaluated_at: datetime,
        authoritative_event_sequence: int,
    ) -> dict[str, Any]:
        _require_command_authority(
            command,
            principal_id=self._host_authority.evaluation_authority.principal_id,
            authority_source=self._host_authority.evaluation_authority.authority_source,
            authority_version=self._host_authority.evaluation_authority.authority_version,
        )
        snapshot_record = self._store.get_authority_snapshot(
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            snapshot_id=snapshot_id,
        )
        if snapshot_record is None:
            raise OutcomeLedgerConflict("completion authority snapshot does not exist")
        _require_not_before("evaluated_at", evaluated_at, snapshot_record["issued_at"])
        _require_not_before("command issued_at", command.issued_at, evaluated_at)
        snapshot = snapshot_record["snapshot"]
        if snapshot.evaluation_authority != self._host_authority.evaluation_authority:
            raise OutcomeLedgerConflict(
                "persisted snapshot does not match configured evaluation authority"
            )
        publication = self._store.get_completion_contract(
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            criteria_id=snapshot.criteria_id,
            criteria_hash=snapshot.criteria_hash,
        )
        if publication is None:
            raise OutcomeLedgerConflict("snapshot criteria are unavailable")
        results = self._results_for_snapshot(command, snapshot)
        evidence = self._evidence_for_results(command, results)
        decision = evaluate_completion(
            decision_id=decision_id,
            criteria=publication["criteria"],
            authority_snapshot=snapshot,
            results=tuple(item["result"] for item in results),
            evidence=tuple(item["evidence"] for item in evidence),
            evaluated_at=evaluated_at,
            authoritative_event_sequence=authoritative_event_sequence,
        )
        decision_hash = completion_decision_digest(decision)
        return self._write(
            self._store.commit_completion_decision,
            command=command,
            command_type="record_completion_decision",
            request_payload={
                "snapshot_id": snapshot_id,
                "snapshot_digest": snapshot_record["snapshot_digest"],
                "decision_digest": decision_hash,
            },
            decision=decision,
            snapshot_id=snapshot_id,
            result_bindings=tuple(
                sorted(
                    (item["result"].result_id, item["result_digest"])
                    for item in results
                )
            ),
            evidence_bindings=tuple(
                sorted(
                    (item["evidence"].evidence_id, item["evidence_digest"])
                    for item in evidence
                )
            ),
        )

    def reproduce_decision(
        self, *, tenant_id: str, workflow_id: str, decision_id: str
    ) -> CompletionDecision:
        bundle = self._store.load_evaluation_bundle(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            decision_id=decision_id,
        )
        if bundle is None:
            raise OutcomeLedgerConflict("completion decision does not exist")
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
        if completion_decision_digest(reproduced) != bundle["decision_digest"]:
            raise OutcomeLedgerConflict(
                "persisted completion decision cannot be reproduced"
            )
        return reproduced

    def _accepted_result_attestations(
        self,
        *,
        command: OutcomeLedgerCommand,
        criteria: CompletionCriteria,
        definitions: tuple[AuthoritativeTaskDefinition, ...],
    ) -> tuple[AcceptedTaskResultAttestation, ...]:
        definitions_by_task = {item.task_id: item for item in definitions}
        attestations: list[AcceptedTaskResultAttestation] = []
        seen_tasks: set[str] = set()
        records = self._store.list_accepted_task_results(
            tenant_id=command.tenant_id,
            workflow_id=command.workflow_id,
            graph_revision=criteria.graph_revision,
        )
        for record in records:
            result = record["result"]
            definition = definitions_by_task.get(result.task_id)
            if definition is None:
                continue
            if result.task_id in seen_tasks:
                raise OutcomeLedgerConflict(
                    "an authority snapshot cannot attest multiple results for one task"
                )
            if (
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
                raise OutcomeLedgerConflict(
                    "accepted result does not match the host task definition"
                )
            if result.validation_authority is None:
                raise OutcomeLedgerConflict(
                    "accepted result lacks validation authority"
                )
            attestations.append(
                AcceptedTaskResultAttestation(
                    task_id=result.task_id,
                    attempt_id=result.attempt_id,
                    assignment_id=result.assignment_id,
                    validation_authority=result.validation_authority,
                    accepted_result_hash=record["result_digest"],
                )
            )
            seen_tasks.add(result.task_id)
        return tuple(sorted(attestations, key=lambda item: item.task_id))

    def _results_for_snapshot(
        self,
        command: OutcomeLedgerCommand,
        snapshot: CompletionAuthoritySnapshot,
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for attestation in snapshot.accepted_result_attestations:
            record = self._store.get_task_result_by_digest(
                tenant_id=command.tenant_id,
                workflow_id=command.workflow_id,
                result_digest=attestation.accepted_result_hash,
            )
            if record is None:
                raise OutcomeLedgerConflict("attested task result is unavailable")
            records.append(record)
        return records

    def _evidence_for_results(
        self,
        command: OutcomeLedgerCommand,
        results: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        evidence_ids = sorted(
            {
                evidence_id
                for record in results
                for evidence_id in record["result"].evidence_ids
            }
        )
        for evidence_id in evidence_ids:
            record = self._store.get_evidence(
                tenant_id=command.tenant_id,
                workflow_id=command.workflow_id,
                evidence_id=evidence_id,
            )
            if record is None:
                raise OutcomeLedgerConflict("result evidence is unavailable")
            records.append(record)
        return records

    def _write(
        self,
        operation,
        *,
        command: OutcomeLedgerCommand,
        command_type: str,
        request_payload: dict[str, object],
        **kwargs: Any,
    ) -> dict[str, Any]:
        request_hash = _request_hash(command_type, request_payload)
        result = operation(
            command=command.persistence_payload(command_type),
            request_hash=request_hash,
            **kwargs,
        )
        if result.get("outcome") == "conflict":
            raise OutcomeLedgerConflict(result.get("reason", "outcome ledger conflict"))
        return result


def _validate_task_definitions(
    criteria: CompletionCriteria,
    definitions: tuple[AuthoritativeTaskDefinition, ...],
) -> None:
    if type(definitions) is not tuple:
        raise OutcomeContractError("task_definitions must be an exact tuple")
    for item in definitions:
        if type(item) is not AuthoritativeTaskDefinition:
            raise OutcomeContractError(
                "task_definitions must contain exact authoritative definitions"
            )
        item.validate()
    task_ids = tuple(item.task_id for item in definitions)
    if task_ids != tuple(sorted(task_ids)) or task_ids != criteria.required_task_ids:
        raise OutcomeContractError(
            "task definitions must exactly match canonical required task membership"
        )


def _definitions_digest(
    definitions: tuple[AuthoritativeTaskDefinition, ...],
) -> str:
    payload = [
        {
            "task_id": item.task_id,
            "task_input_hash": item.task_input_hash,
            "result_schema_id": item.result_schema_id,
            "result_schema_version": item.result_schema_version,
            "result_schema_hash": item.result_schema_hash,
        }
        for item in definitions
    ]
    return _json_digest(payload)


def _request_hash(command_type: str, payload: dict[str, object]) -> str:
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


def _require_scope(
    command: OutcomeLedgerCommand, tenant_id: str, workflow_id: str
) -> None:
    if (command.tenant_id, command.workflow_id) != (tenant_id, workflow_id):
        raise OutcomeContractError("command scope must match artifact scope")


def _require_not_before(name: str, value: datetime, lower_bound: datetime) -> None:
    _format_utc(value)
    _format_utc(lower_bound)
    if value < lower_bound:
        raise OutcomeContractError(f"{name} cannot precede durable artifact time")


def _require_command_authority(
    command: OutcomeLedgerCommand,
    *,
    principal_id: str,
    authority_source: str,
    authority_version: str,
) -> None:
    if (
        command.principal_id,
        command.authority_source,
        command.authority_version,
    ) != (principal_id, authority_source, authority_version):
        raise OutcomeContractError(
            "command authority does not match artifact authority"
        )


def _require_identifier(field_name: str, value: object) -> None:
    if type(value) is not str or not value or value != value.strip():
        raise OutcomeContractError(
            f"{field_name} must be a non-empty canonical exact string"
        )


def _require_identifier_tuple(field_name: str, value: object) -> None:
    if type(value) is not tuple:
        raise OutcomeContractError(f"{field_name} must be an exact tuple")
    if any(type(item) is not str or not item or item != item.strip() for item in value):
        raise OutcomeContractError(f"{field_name} must contain canonical identifiers")
    if len(set(value)) != len(value) or tuple(sorted(value)) != value:
        raise OutcomeContractError(f"{field_name} must be unique and canonical")


def _format_utc(value: datetime) -> str:
    if type(value) is not datetime or type(value.tzinfo) is not timezone:
        raise OutcomeContractError("issued_at must use immutable UTC timezone")
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = ["WorkflowOutcomeService"]
