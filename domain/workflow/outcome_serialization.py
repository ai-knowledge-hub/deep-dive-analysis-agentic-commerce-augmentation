"""Canonical schema-v1 serialization for workflow outcome contracts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, TypeVar, cast

from domain.workflow.outcomes import (
    COMPLETION_CRITERIA_CONTRACT,
    COMPLETION_DECISION_CONTRACT,
    EVIDENCE_CONTRACT,
    OUTCOME_SCHEMA_VERSION,
    RESULT_CONTRACT,
    CompletionCriteria,
    CompletionDecision,
    CompletionStatus,
    ContractAuthority,
    CoverageClaim,
    CoverageStatus,
    EvidenceAvailability,
    EvidenceProvenance,
    EvidenceRecord,
    EvidenceRequirement,
    OutcomeContractError,
    ReceiptStatus,
    ResultOutcome,
    ResultValidationAuthority,
    ResultValidationStatus,
    TaskResult,
)


_EnumT = TypeVar("_EnumT", bound=Enum)


def evidence_payload(value: EvidenceRecord) -> dict[str, Any]:
    _require_exact_type("evidence", value, EvidenceRecord)
    return cast(dict[str, Any], value.canonical_payload())


def evidence_from_payload(value: dict[str, Any]) -> EvidenceRecord:
    top = _mapping("evidence", value)
    _keys(
        "evidence",
        top,
        {"contract", "schema_version", "evidence_id", "scope", "observation"},
    )
    _contract(top, EVIDENCE_CONTRACT)
    scope = _mapping("scope", top["scope"])
    _keys(
        "scope",
        scope,
        {
            "tenant_id",
            "workflow_id",
            "graph_revision",
            "task_id",
            "attempt_id",
            "action_id",
        },
    )
    observation = _mapping("observation", top["observation"])
    _keys(
        "observation",
        observation,
        {
            "availability",
            "content_hash",
            "provenance",
            "receipt_status",
            "receipt_id",
            "observed_at",
            "valid_until",
            "recorded_at",
            "failure_code",
        },
    )
    provenance = _mapping("provenance", observation["provenance"])
    _keys(
        "provenance",
        provenance,
        {
            "source_type",
            "source_id",
            "source_version",
            "source_contract_hash",
            "producer_principal_id",
            "capability_id",
            "tool_id",
        },
    )
    return EvidenceRecord(
        evidence_id=top["evidence_id"],
        schema_version=top["schema_version"],
        tenant_id=scope["tenant_id"],
        workflow_id=scope["workflow_id"],
        graph_revision=scope["graph_revision"],
        task_id=scope["task_id"],
        attempt_id=scope["attempt_id"],
        action_id=scope["action_id"],
        availability=_enum(EvidenceAvailability, observation["availability"]),
        content_hash=observation["content_hash"],
        provenance=EvidenceProvenance(**provenance),
        receipt_status=_enum(ReceiptStatus, observation["receipt_status"]),
        receipt_id=observation["receipt_id"],
        observed_at=_optional_datetime("observed_at", observation["observed_at"]),
        valid_until=_optional_datetime("valid_until", observation["valid_until"]),
        recorded_at=_datetime("recorded_at", observation["recorded_at"]),
        failure_code=observation["failure_code"],
    )


def completion_criteria_payload(value: CompletionCriteria) -> dict[str, Any]:
    _require_exact_type("criteria", value, CompletionCriteria)
    return cast(dict[str, Any], value.canonical_payload())


def completion_criteria_from_payload(value: dict[str, Any]) -> CompletionCriteria:
    top = _mapping("criteria", value)
    _keys(
        "criteria",
        top,
        {
            "contract",
            "schema_version",
            "criteria_id",
            "scope",
            "criteria_version",
            "publishing_authority",
            "authority_hash",
            "required_task_ids",
            "evidence_requirements",
            "created_at",
        },
    )
    _contract(top, COMPLETION_CRITERIA_CONTRACT)
    scope = _mapping("scope", top["scope"])
    _keys(
        "scope", scope, {"tenant_id", "workflow_id", "graph_revision", "objective_id"}
    )
    requirements = _list("evidence_requirements", top["evidence_requirements"])
    parsed_requirements: list[EvidenceRequirement] = []
    expected_requirement_keys = {
        "requirement_id",
        "task_id",
        "min_items",
        "max_age_seconds",
        "require_verified_receipt",
        "allowed_source_types",
    }
    for raw in requirements:
        item = _mapping("evidence requirement", raw)
        _keys("evidence requirement", item, expected_requirement_keys)
        parsed_requirements.append(
            EvidenceRequirement(
                requirement_id=item["requirement_id"],
                task_id=item["task_id"],
                min_items=item["min_items"],
                max_age_seconds=item["max_age_seconds"],
                require_verified_receipt=item["require_verified_receipt"],
                allowed_source_types=_string_tuple(
                    "allowed_source_types", item["allowed_source_types"]
                ),
            )
        )
    return CompletionCriteria(
        criteria_id=top["criteria_id"],
        schema_version=top["schema_version"],
        tenant_id=scope["tenant_id"],
        workflow_id=scope["workflow_id"],
        graph_revision=scope["graph_revision"],
        objective_id=scope["objective_id"],
        criteria_version=top["criteria_version"],
        publishing_authority=_authority_from_payload(
            "publishing_authority", top["publishing_authority"]
        ),
        authority_hash=top["authority_hash"],
        required_task_ids=_string_tuple("required_task_ids", top["required_task_ids"]),
        evidence_requirements=tuple(parsed_requirements),
        created_at=_datetime("created_at", top["created_at"]),
    )


def task_result_payload(value: TaskResult) -> dict[str, Any]:
    _require_exact_type("result", value, TaskResult)
    value.validate()
    authority = value.validation_authority
    return {
        "contract": RESULT_CONTRACT,
        "schema_version": value.schema_version,
        "result_id": value.result_id,
        "scope": {
            "tenant_id": value.tenant_id,
            "workflow_id": value.workflow_id,
            "graph_revision": value.graph_revision,
            "task_id": value.task_id,
            "attempt_id": value.attempt_id,
            "assignment_id": value.assignment_id,
        },
        "result_schema_id": value.result_schema_id,
        "result_schema_version": value.result_schema_version,
        "task_input_hash": value.task_input_hash,
        "result_schema_hash": value.result_schema_hash,
        "producer_principal_id": value.producer_principal_id,
        "outcome": value.outcome.value,
        "payload_hash": value.payload_hash,
        "evidence_ids": list(value.evidence_ids),
        "evidence_digest": value.evidence_digest,
        "coverage": [
            {
                "requirement_id": item.requirement_id,
                "status": item.status.value,
                "evidence_ids": list(item.evidence_ids),
            }
            for item in value.coverage
        ],
        "validation": {
            "status": value.validation_status.value,
            "authority": None
            if authority is None
            else {
                "principal_id": authority.principal_id,
                "authority_source": authority.authority_source,
                "authority_version": authority.authority_version,
            },
            "validated_at": _format_optional_datetime(value.validated_at),
        },
        "created_at": _format_datetime(value.created_at),
        "error_code": value.error_code,
    }


def task_result_from_payload(value: dict[str, Any]) -> TaskResult:
    top = _mapping("result", value)
    _keys(
        "result",
        top,
        {
            "contract",
            "schema_version",
            "result_id",
            "scope",
            "result_schema_id",
            "result_schema_version",
            "task_input_hash",
            "result_schema_hash",
            "producer_principal_id",
            "outcome",
            "payload_hash",
            "evidence_ids",
            "evidence_digest",
            "coverage",
            "validation",
            "created_at",
            "error_code",
        },
    )
    _contract(top, RESULT_CONTRACT)
    scope = _mapping("scope", top["scope"])
    _keys(
        "scope",
        scope,
        {
            "tenant_id",
            "workflow_id",
            "graph_revision",
            "task_id",
            "attempt_id",
            "assignment_id",
        },
    )
    validation = _mapping("validation", top["validation"])
    _keys("validation", validation, {"status", "authority", "validated_at"})
    authority_value = validation["authority"]
    authority = None
    if authority_value is not None:
        authority_map = _mapping("validation authority", authority_value)
        _keys(
            "validation authority",
            authority_map,
            {"principal_id", "authority_source", "authority_version"},
        )
        authority = ResultValidationAuthority(**authority_map)
    coverage: list[CoverageClaim] = []
    for raw in _list("coverage", top["coverage"]):
        item = _mapping("coverage claim", raw)
        _keys("coverage claim", item, {"requirement_id", "status", "evidence_ids"})
        coverage.append(
            CoverageClaim(
                requirement_id=item["requirement_id"],
                status=_enum(CoverageStatus, item["status"]),
                evidence_ids=_string_tuple("evidence_ids", item["evidence_ids"]),
            )
        )
    return TaskResult(
        result_id=top["result_id"],
        schema_version=top["schema_version"],
        tenant_id=scope["tenant_id"],
        workflow_id=scope["workflow_id"],
        graph_revision=scope["graph_revision"],
        task_id=scope["task_id"],
        attempt_id=scope["attempt_id"],
        assignment_id=scope["assignment_id"],
        task_input_hash=top["task_input_hash"],
        result_schema_id=top["result_schema_id"],
        result_schema_version=top["result_schema_version"],
        result_schema_hash=top["result_schema_hash"],
        producer_principal_id=top["producer_principal_id"],
        outcome=_enum(ResultOutcome, top["outcome"]),
        payload_hash=top["payload_hash"],
        evidence_ids=_string_tuple("evidence_ids", top["evidence_ids"]),
        evidence_digest=top["evidence_digest"],
        coverage=tuple(coverage),
        validation_status=_enum(ResultValidationStatus, validation["status"]),
        validation_authority=authority,
        validated_at=_optional_datetime("validated_at", validation["validated_at"]),
        created_at=_datetime("created_at", top["created_at"]),
        error_code=top["error_code"],
    )


def completion_decision_payload(value: CompletionDecision) -> dict[str, Any]:
    _require_exact_type("decision", value, CompletionDecision)
    return cast(dict[str, Any], value.canonical_payload())


def completion_decision_from_payload(value: dict[str, Any]) -> CompletionDecision:
    top = _mapping("decision", value)
    _keys(
        "decision",
        top,
        {
            "contract",
            "schema_version",
            "decision_id",
            "scope",
            "criteria_id",
            "criteria_hash",
            "evaluation_authority",
            "status",
            "accepted_result_ids",
            "evidence_ids",
            "blockers",
            "evaluated_at",
            "authoritative_event_sequence",
        },
    )
    _contract(top, COMPLETION_DECISION_CONTRACT)
    scope = _mapping("scope", top["scope"])
    _keys(
        "scope", scope, {"tenant_id", "workflow_id", "graph_revision", "objective_id"}
    )
    blockers = _mapping("blockers", top["blockers"])
    _keys(
        "blockers",
        blockers,
        {
            "missing_requirement_ids",
            "unavailable_requirement_ids",
            "contradictory_requirement_ids",
            "stale_evidence_ids",
            "unverified_evidence_ids",
            "invalid_evidence_ids",
            "missing_result_task_ids",
            "partial_task_ids",
            "failed_task_ids",
            "canceled_task_ids",
        },
    )
    return CompletionDecision(
        decision_id=top["decision_id"],
        schema_version=top["schema_version"],
        tenant_id=scope["tenant_id"],
        workflow_id=scope["workflow_id"],
        graph_revision=scope["graph_revision"],
        objective_id=scope["objective_id"],
        criteria_id=top["criteria_id"],
        criteria_hash=top["criteria_hash"],
        evaluation_authority=_authority_from_payload(
            "evaluation_authority", top["evaluation_authority"]
        ),
        status=_enum(CompletionStatus, top["status"]),
        accepted_result_ids=_string_tuple(
            "accepted_result_ids", top["accepted_result_ids"]
        ),
        evidence_ids=_string_tuple("evidence_ids", top["evidence_ids"]),
        missing_requirement_ids=_string_tuple(
            "missing_requirement_ids", blockers["missing_requirement_ids"]
        ),
        unavailable_requirement_ids=_string_tuple(
            "unavailable_requirement_ids",
            blockers["unavailable_requirement_ids"],
        ),
        contradictory_requirement_ids=_string_tuple(
            "contradictory_requirement_ids",
            blockers["contradictory_requirement_ids"],
        ),
        stale_evidence_ids=_string_tuple(
            "stale_evidence_ids", blockers["stale_evidence_ids"]
        ),
        unverified_evidence_ids=_string_tuple(
            "unverified_evidence_ids", blockers["unverified_evidence_ids"]
        ),
        invalid_evidence_ids=_string_tuple(
            "invalid_evidence_ids", blockers["invalid_evidence_ids"]
        ),
        missing_result_task_ids=_string_tuple(
            "missing_result_task_ids", blockers["missing_result_task_ids"]
        ),
        partial_task_ids=_string_tuple(
            "partial_task_ids", blockers["partial_task_ids"]
        ),
        failed_task_ids=_string_tuple("failed_task_ids", blockers["failed_task_ids"]),
        canceled_task_ids=_string_tuple(
            "canceled_task_ids", blockers["canceled_task_ids"]
        ),
        evaluated_at=_datetime("evaluated_at", top["evaluated_at"]),
        authoritative_event_sequence=top["authoritative_event_sequence"],
    )


def evidence_digest(value: EvidenceRecord) -> str:
    return _digest(evidence_payload(value))


def completion_criteria_digest(value: CompletionCriteria) -> str:
    return _digest(completion_criteria_payload(value))


def task_result_digest(value: TaskResult) -> str:
    return _digest(task_result_payload(value))


def completion_decision_digest(value: CompletionDecision) -> str:
    return _digest(completion_decision_payload(value))


def _digest(value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _format_datetime(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _authority_from_payload(field_name: str, value: object) -> ContractAuthority:
    authority = _mapping(field_name, value)
    _keys(
        field_name,
        authority,
        {"principal_id", "authority_source", "authority_version"},
    )
    return ContractAuthority(**authority)


def _format_optional_datetime(value: datetime | None) -> str | None:
    return None if value is None else _format_datetime(value)


def _datetime(field_name: str, value: object) -> datetime:
    if type(value) is not str:
        raise OutcomeContractError(f"{field_name} must be canonical timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise OutcomeContractError(f"{field_name} must be canonical timestamp") from exc
    if parsed.utcoffset() is None or _format_datetime(parsed) != value:
        raise OutcomeContractError(f"{field_name} must use canonical UTC encoding")
    return parsed


def _optional_datetime(field_name: str, value: object) -> datetime | None:
    return None if value is None else _datetime(field_name, value)


def _mapping(field_name: str, value: object) -> dict[str, Any]:
    if type(value) is not dict:
        raise OutcomeContractError(f"{field_name} must be an exact object")
    return cast(dict[str, Any], value)


def _list(field_name: str, value: object) -> list[Any]:
    if type(value) is not list:
        raise OutcomeContractError(f"{field_name} must be an exact array")
    return cast(list[Any], value)


def _string_tuple(field_name: str, value: object) -> tuple[str, ...]:
    items = _list(field_name, value)
    if any(type(item) is not str for item in items):
        raise OutcomeContractError(f"{field_name} items must be exact strings")
    return tuple(items)


def _keys(field_name: str, value: dict[str, Any], expected: set[str]) -> None:
    if any(type(key) is not str for key in value):
        raise OutcomeContractError(f"{field_name} keys must be exact strings")
    actual = set(value)
    if actual != expected:
        raise OutcomeContractError(
            f"{field_name} fields must match schema v1; "
            f"missing={sorted(expected - actual)}, unknown={sorted(actual - expected)}"
        )


def _contract(value: dict[str, Any], expected: str) -> None:
    if type(value["contract"]) is not str or value["contract"] != expected:
        raise OutcomeContractError(f"unsupported contract; expected {expected}")
    if (
        type(value["schema_version"]) is not str
        or value["schema_version"] != OUTCOME_SCHEMA_VERSION
    ):
        raise OutcomeContractError("unsupported outcome schema_version")


def _enum(enum_type: type[_EnumT], value: object) -> _EnumT:
    if type(value) is not str:
        raise OutcomeContractError(
            f"{enum_type.__name__} must be encoded as exact string"
        )
    try:
        return enum_type(value)
    except ValueError as exc:
        raise OutcomeContractError(
            f"unsupported {enum_type.__name__} value {value!r}"
        ) from exc


def _require_exact_type(field_name: str, value: object, expected: type[object]) -> None:
    if type(value) is not expected:
        raise OutcomeContractError(f"{field_name} must be exact {expected.__name__}")


__all__ = [
    "completion_criteria_digest",
    "completion_criteria_from_payload",
    "completion_criteria_payload",
    "completion_decision_digest",
    "completion_decision_from_payload",
    "completion_decision_payload",
    "evidence_digest",
    "evidence_from_payload",
    "evidence_payload",
    "task_result_digest",
    "task_result_from_payload",
    "task_result_payload",
]
