"""Pure evidence, task-result, and objective-completion contracts."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Final


EVIDENCE_CONTRACT: Final = "workflow.evidence"
RESULT_CONTRACT: Final = "workflow.task-result"
COMPLETION_CRITERIA_CONTRACT: Final = "workflow.completion-criteria"
COMPLETION_DECISION_CONTRACT: Final = "workflow.completion-decision"
OUTCOME_SCHEMA_VERSION: Final = "1.0"

_DIGEST_PATTERN = re.compile(r"[0-9a-f]{64}")


class OutcomeContractError(ValueError):
    """Raised when an outcome object violates the domain contract."""


class EvidenceAvailability(str, Enum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ReceiptStatus(str, Enum):
    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNCERTAIN = "uncertain"


class CoverageStatus(str, Enum):
    SATISFIED = "satisfied"
    MISSING = "missing"
    UNAVAILABLE = "unavailable"
    CONTRADICTORY = "contradictory"


class ResultOutcome(str, Enum):
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELED = "canceled"


class ResultValidationStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class CompletionStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class CompletionDisplayStatus(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"
    STALE = "stale"


@dataclass(frozen=True)
class ContractAuthority:
    """Identified authority that publishes criteria or evaluates completion."""

    principal_id: str
    authority_source: str
    authority_version: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field_name in (
            "principal_id",
            "authority_source",
            "authority_version",
        ):
            _require_identifier(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class EvidenceProvenance:
    """Authority and executable source that produced an observation."""

    source_type: str
    source_id: str
    source_version: str
    source_contract_hash: str
    producer_principal_id: str
    capability_id: str
    tool_id: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field_name in (
            "source_type",
            "source_id",
            "source_version",
            "producer_principal_id",
            "capability_id",
            "tool_id",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_digest("source_contract_hash", self.source_contract_hash)


@dataclass(frozen=True)
class EvidenceRecord:
    """Immutable observation; it does not claim objective completeness."""

    evidence_id: str
    schema_version: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    task_id: str
    attempt_id: str
    action_id: str | None
    availability: EvidenceAvailability
    content_hash: str | None
    provenance: EvidenceProvenance
    receipt_status: ReceiptStatus
    receipt_id: str | None
    observed_at: datetime | None
    valid_until: datetime | None
    recorded_at: datetime
    failure_code: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_schema(self.schema_version)
        for field_name in (
            "evidence_id",
            "tenant_id",
            "workflow_id",
            "task_id",
            "attempt_id",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_optional_identifier("action_id", self.action_id)
        _require_positive_int("graph_revision", self.graph_revision)
        _require_enum("availability", self.availability, EvidenceAvailability)
        _require_enum("receipt_status", self.receipt_status, ReceiptStatus)
        if type(self.provenance) is not EvidenceProvenance:
            raise OutcomeContractError("provenance must be EvidenceProvenance")
        self.provenance.validate()
        recorded_at = _normalize_datetime("recorded_at", self.recorded_at)
        object.__setattr__(self, "recorded_at", recorded_at)
        _validate_receipt(self)
        if self.availability is EvidenceAvailability.AVAILABLE:
            _require_digest("content_hash", self.content_hash)
            observed_at = _normalize_datetime("observed_at", self.observed_at)
            valid_until = _normalize_datetime("valid_until", self.valid_until)
            object.__setattr__(self, "observed_at", observed_at)
            object.__setattr__(self, "valid_until", valid_until)
            if valid_until <= observed_at:
                raise OutcomeContractError("valid_until must be after observed_at")
            if recorded_at < observed_at:
                raise OutcomeContractError("recorded_at cannot be before observed_at")
            if self.failure_code is not None:
                raise OutcomeContractError(
                    "available evidence cannot contain failure_code"
                )
        else:
            if any(
                value is not None
                for value in (self.content_hash, self.observed_at, self.valid_until)
            ):
                raise OutcomeContractError(
                    "unavailable evidence cannot contain observed content or validity"
                )
            _require_identifier("failure_code", self.failure_code)
            if self.receipt_status is not ReceiptStatus.NOT_REQUIRED:
                raise OutcomeContractError(
                    "unavailable evidence cannot claim a provider receipt"
                )

    def is_fresh_at(self, value: datetime) -> bool:
        """Return freshness at an exact evaluation instant."""

        instant = _normalize_datetime("freshness instant", value)
        return bool(
            self.availability is EvidenceAvailability.AVAILABLE
            and self.observed_at is not None
            and self.valid_until is not None
            and self.observed_at <= instant < self.valid_until
        )

    def canonical_payload(self) -> dict[str, object]:
        """Return the unique schema-v1 evidence representation."""

        self.validate()
        return {
            "contract": EVIDENCE_CONTRACT,
            "schema_version": self.schema_version,
            "evidence_id": self.evidence_id,
            "scope": {
                "tenant_id": self.tenant_id,
                "workflow_id": self.workflow_id,
                "graph_revision": self.graph_revision,
                "task_id": self.task_id,
                "attempt_id": self.attempt_id,
                "action_id": self.action_id,
            },
            "observation": {
                "availability": self.availability.value,
                "content_hash": self.content_hash,
                "provenance": {
                    "source_type": self.provenance.source_type,
                    "source_id": self.provenance.source_id,
                    "source_version": self.provenance.source_version,
                    "source_contract_hash": self.provenance.source_contract_hash,
                    "producer_principal_id": self.provenance.producer_principal_id,
                    "capability_id": self.provenance.capability_id,
                    "tool_id": self.provenance.tool_id,
                },
                "receipt_status": self.receipt_status.value,
                "receipt_id": self.receipt_id,
                "observed_at": _format_optional_datetime(self.observed_at),
                "valid_until": _format_optional_datetime(self.valid_until),
                "recorded_at": _format_datetime(self.recorded_at),
                "failure_code": self.failure_code,
            },
        }


@dataclass(frozen=True)
class EvidenceRequirement:
    """Independent criterion that evidence supplied by a task must satisfy."""

    requirement_id: str
    task_id: str
    min_items: int
    max_age_seconds: int
    require_verified_receipt: bool
    allowed_source_types: tuple[str, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_identifier("requirement_id", self.requirement_id)
        _require_identifier("task_id", self.task_id)
        _require_positive_int("min_items", self.min_items)
        _require_positive_int("max_age_seconds", self.max_age_seconds)
        if type(self.require_verified_receipt) is not bool:
            raise OutcomeContractError("require_verified_receipt must be exact bool")
        _require_identifier_tuple(
            "allowed_source_types", self.allowed_source_types, allow_empty=False
        )


@dataclass(frozen=True)
class CompletionCriteria:
    """Versioned, independently authoritative objective-completion requirements."""

    criteria_id: str
    schema_version: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    objective_id: str
    criteria_version: str
    publishing_authority: ContractAuthority
    authority_hash: str
    required_task_ids: tuple[str, ...]
    evidence_requirements: tuple[EvidenceRequirement, ...]
    created_at: datetime

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_schema(self.schema_version)
        for field_name in (
            "criteria_id",
            "tenant_id",
            "workflow_id",
            "objective_id",
            "criteria_version",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_positive_int("graph_revision", self.graph_revision)
        if type(self.publishing_authority) is not ContractAuthority:
            raise OutcomeContractError("publishing_authority must be ContractAuthority")
        self.publishing_authority.validate()
        _require_digest("authority_hash", self.authority_hash)
        _require_identifier_tuple(
            "required_task_ids", self.required_task_ids, allow_empty=False
        )
        if type(self.evidence_requirements) is not tuple:
            raise OutcomeContractError("evidence_requirements must be exact tuple")
        requirement_ids: list[str] = []
        for requirement in self.evidence_requirements:
            if type(requirement) is not EvidenceRequirement:
                raise OutcomeContractError(
                    "evidence_requirements must contain EvidenceRequirement values"
                )
            requirement.validate()
            if requirement.task_id not in self.required_task_ids:
                raise OutcomeContractError(
                    "evidence requirement task must be independently required"
                )
            requirement_ids.append(requirement.requirement_id)
        _require_unique("evidence requirement IDs", requirement_ids)
        if requirement_ids != sorted(requirement_ids):
            raise OutcomeContractError(
                "evidence_requirements must use canonical requirement_id order"
            )
        object.__setattr__(
            self, "created_at", _normalize_datetime("created_at", self.created_at)
        )

    def canonical_payload(self) -> dict[str, object]:
        """Return the unique schema-v1 representation used for its authority hash."""

        self.validate()
        return {
            "contract": COMPLETION_CRITERIA_CONTRACT,
            "schema_version": self.schema_version,
            "criteria_id": self.criteria_id,
            "scope": {
                "tenant_id": self.tenant_id,
                "workflow_id": self.workflow_id,
                "graph_revision": self.graph_revision,
                "objective_id": self.objective_id,
            },
            "criteria_version": self.criteria_version,
            "publishing_authority": _contract_authority_payload(
                self.publishing_authority
            ),
            "authority_hash": self.authority_hash,
            "required_task_ids": list(self.required_task_ids),
            "evidence_requirements": [
                {
                    "requirement_id": item.requirement_id,
                    "task_id": item.task_id,
                    "min_items": item.min_items,
                    "max_age_seconds": item.max_age_seconds,
                    "require_verified_receipt": item.require_verified_receipt,
                    "allowed_source_types": list(item.allowed_source_types),
                }
                for item in self.evidence_requirements
            ],
            "created_at": _format_datetime(self.created_at),
        }


@dataclass(frozen=True)
class CoverageClaim:
    """A task result's explicit claim about one independently named requirement."""

    requirement_id: str
    status: CoverageStatus
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_identifier("requirement_id", self.requirement_id)
        _require_enum("coverage status", self.status, CoverageStatus)
        _require_identifier_tuple("evidence_ids", self.evidence_ids, allow_empty=True)
        if self.status is CoverageStatus.SATISFIED and not self.evidence_ids:
            raise OutcomeContractError("satisfied coverage requires evidence")
        if self.status is CoverageStatus.MISSING and self.evidence_ids:
            raise OutcomeContractError("missing coverage cannot cite evidence")


@dataclass(frozen=True)
class ResultValidationAuthority:
    """Coordinator authority that accepted or rejected a returned result."""

    principal_id: str
    authority_source: str
    authority_version: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field_name in (
            "principal_id",
            "authority_source",
            "authority_version",
        ):
            _require_identifier(field_name, getattr(self, field_name))


@dataclass(frozen=True)
class AuthoritativeTaskDefinition:
    """Host-owned task input and result-schema contract."""

    task_id: str
    task_input_hash: str
    result_schema_id: str
    result_schema_version: str
    result_schema_hash: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field_name in (
            "task_id",
            "result_schema_id",
            "result_schema_version",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_digest("task_input_hash", self.task_input_hash)
        _require_digest("result_schema_hash", self.result_schema_hash)


@dataclass(frozen=True)
class AcceptedTaskResultAttestation:
    """Optional host attestation created only after result acceptance."""

    task_id: str
    attempt_id: str
    assignment_id: str | None
    validation_authority: ResultValidationAuthority
    accepted_result_hash: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_identifier("task_id", self.task_id)
        _require_identifier("attempt_id", self.attempt_id)
        _require_optional_identifier("assignment_id", self.assignment_id)
        _require_digest("accepted_result_hash", self.accepted_result_hash)
        if type(self.validation_authority) is not ResultValidationAuthority:
            raise OutcomeContractError(
                "validation_authority must be ResultValidationAuthority"
            )
        self.validation_authority.validate()


@dataclass(frozen=True)
class CompletionAuthoritySnapshot:
    """Host-read authority oracle, separate from worker-submitted objects."""

    tenant_id: str
    workflow_id: str
    graph_revision: int
    objective_id: str
    criteria_id: str
    criteria_hash: str
    criteria_authority_hash: str
    publishing_authority: ContractAuthority
    evaluation_authority: ContractAuthority
    task_definitions: tuple[AuthoritativeTaskDefinition, ...]
    accepted_result_attestations: tuple[AcceptedTaskResultAttestation, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        for field_name in (
            "tenant_id",
            "workflow_id",
            "objective_id",
            "criteria_id",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_positive_int("graph_revision", self.graph_revision)
        _require_digest("criteria_hash", self.criteria_hash)
        _require_digest("criteria_authority_hash", self.criteria_authority_hash)
        for name in ("publishing_authority", "evaluation_authority"):
            authority = getattr(self, name)
            if type(authority) is not ContractAuthority:
                raise OutcomeContractError(f"{name} must be ContractAuthority")
            authority.validate()
        _require_exact_tuple("task_definitions", self.task_definitions)
        task_ids: list[str] = []
        for definition in self.task_definitions:
            if type(definition) is not AuthoritativeTaskDefinition:
                raise OutcomeContractError(
                    "task_definitions must contain exact authoritative definitions"
                )
            definition.validate()
            task_ids.append(definition.task_id)
        _require_unique("authoritative task IDs", task_ids)
        if task_ids != sorted(task_ids):
            raise OutcomeContractError(
                "task_definitions must use canonical task_id order"
            )
        _require_exact_tuple(
            "accepted_result_attestations", self.accepted_result_attestations
        )
        attested_task_ids: list[str] = []
        for attestation in self.accepted_result_attestations:
            if type(attestation) is not AcceptedTaskResultAttestation:
                raise OutcomeContractError(
                    "accepted_result_attestations must contain exact attestations"
                )
            attestation.validate()
            attested_task_ids.append(attestation.task_id)
        _require_unique("attested task IDs", attested_task_ids)
        if attested_task_ids != sorted(attested_task_ids):
            raise OutcomeContractError(
                "accepted_result_attestations must use canonical task_id order"
            )
        if not set(attested_task_ids).issubset(set(task_ids)):
            raise OutcomeContractError(
                "accepted result attestations require authoritative task definitions"
            )


@dataclass(frozen=True)
class TaskResult:
    """Immutable task-attempt output awaiting or carrying coordinator validation."""

    result_id: str
    schema_version: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    task_id: str
    attempt_id: str
    assignment_id: str | None
    task_input_hash: str
    result_schema_id: str
    result_schema_version: str
    result_schema_hash: str
    producer_principal_id: str
    outcome: ResultOutcome
    payload_hash: str | None
    evidence_ids: tuple[str, ...]
    evidence_digest: str
    coverage: tuple[CoverageClaim, ...]
    validation_status: ResultValidationStatus
    validation_authority: ResultValidationAuthority | None
    validated_at: datetime | None
    created_at: datetime
    error_code: str | None = None

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_schema(self.schema_version)
        for field_name in (
            "result_id",
            "tenant_id",
            "workflow_id",
            "task_id",
            "attempt_id",
            "result_schema_id",
            "result_schema_version",
            "producer_principal_id",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_optional_identifier("assignment_id", self.assignment_id)
        _require_positive_int("graph_revision", self.graph_revision)
        _require_digest("task_input_hash", self.task_input_hash)
        _require_digest("result_schema_hash", self.result_schema_hash)
        _require_digest("evidence_digest", self.evidence_digest)
        _require_enum("outcome", self.outcome, ResultOutcome)
        _require_enum(
            "validation_status", self.validation_status, ResultValidationStatus
        )
        _require_identifier_tuple("evidence_ids", self.evidence_ids, allow_empty=True)
        _validate_coverage(self)
        created_at = _normalize_datetime("created_at", self.created_at)
        object.__setattr__(self, "created_at", created_at)
        if self.outcome in {ResultOutcome.SUCCEEDED, ResultOutcome.PARTIAL}:
            _require_digest("payload_hash", self.payload_hash)
            if self.error_code is not None:
                raise OutcomeContractError(
                    "successful or partial result cannot contain error_code"
                )
        else:
            _require_identifier("error_code", self.error_code)
        if self.outcome is ResultOutcome.SUCCEEDED and any(
            claim.status is not CoverageStatus.SATISFIED for claim in self.coverage
        ):
            raise OutcomeContractError(
                "succeeded result cannot report unsatisfied coverage"
            )
        if self.outcome is ResultOutcome.PARTIAL and not any(
            claim.status is not CoverageStatus.SATISFIED for claim in self.coverage
        ):
            raise OutcomeContractError(
                "partial result must report at least one unsatisfied requirement"
            )
        has_validation = self.validation_authority is not None
        if has_validation != (self.validated_at is not None):
            raise OutcomeContractError(
                "validation_authority and validated_at must be present together"
            )
        if self.validation_status is ResultValidationStatus.PENDING:
            if has_validation:
                raise OutcomeContractError(
                    "pending result cannot contain validation authority"
                )
        elif not has_validation:
            raise OutcomeContractError(
                "accepted or rejected result requires validation authority"
            )
        if self.validation_authority is not None:
            if type(self.validation_authority) is not ResultValidationAuthority:
                raise OutcomeContractError(
                    "validation_authority must be ResultValidationAuthority"
                )
            self.validation_authority.validate()
            if self.validation_authority.principal_id == self.producer_principal_id:
                raise OutcomeContractError(
                    "result producer cannot validate its own result"
                )
            validated_at = _normalize_datetime("validated_at", self.validated_at)
            object.__setattr__(self, "validated_at", validated_at)
            if validated_at < created_at:
                raise OutcomeContractError("validated_at cannot precede created_at")


@dataclass(frozen=True)
class CompletionDecision:
    """Authoritative evaluation of results against independent criteria."""

    decision_id: str
    schema_version: str
    tenant_id: str
    workflow_id: str
    graph_revision: int
    objective_id: str
    criteria_id: str
    criteria_hash: str
    evaluation_authority: ContractAuthority
    status: CompletionStatus
    accepted_result_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    missing_requirement_ids: tuple[str, ...]
    unavailable_requirement_ids: tuple[str, ...]
    contradictory_requirement_ids: tuple[str, ...]
    stale_evidence_ids: tuple[str, ...]
    unverified_evidence_ids: tuple[str, ...]
    invalid_evidence_ids: tuple[str, ...]
    missing_result_task_ids: tuple[str, ...]
    partial_task_ids: tuple[str, ...]
    failed_task_ids: tuple[str, ...]
    canceled_task_ids: tuple[str, ...]
    evaluated_at: datetime
    authoritative_event_sequence: int

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        _require_schema(self.schema_version)
        for field_name in (
            "decision_id",
            "tenant_id",
            "workflow_id",
            "objective_id",
            "criteria_id",
        ):
            _require_identifier(field_name, getattr(self, field_name))
        _require_positive_int("graph_revision", self.graph_revision)
        _require_digest("criteria_hash", self.criteria_hash)
        if type(self.evaluation_authority) is not ContractAuthority:
            raise OutcomeContractError("evaluation_authority must be ContractAuthority")
        self.evaluation_authority.validate()
        _require_enum("status", self.status, CompletionStatus)
        for field_name in (
            "accepted_result_ids",
            "evidence_ids",
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
        ):
            _require_identifier_tuple(
                field_name, getattr(self, field_name), allow_empty=True
            )
        _require_nonnegative_int(
            "authoritative_event_sequence", self.authoritative_event_sequence
        )
        object.__setattr__(
            self,
            "evaluated_at",
            _normalize_datetime("evaluated_at", self.evaluated_at),
        )
        blockers = (
            self.missing_requirement_ids
            or self.unavailable_requirement_ids
            or self.contradictory_requirement_ids
            or self.stale_evidence_ids
            or self.unverified_evidence_ids
            or self.invalid_evidence_ids
            or self.missing_result_task_ids
            or self.partial_task_ids
            or self.failed_task_ids
            or self.canceled_task_ids
        )
        if self.status is CompletionStatus.COMPLETE and blockers:
            raise OutcomeContractError("complete decision cannot contain blockers")
        if self.status is CompletionStatus.COMPLETE and not self.accepted_result_ids:
            raise OutcomeContractError(
                "complete decision must identify accepted results"
            )
        if self.status is CompletionStatus.INCOMPLETE and not blockers:
            raise OutcomeContractError("incomplete decision must identify blockers")

    def canonical_payload(self) -> dict[str, object]:
        """Return the unique schema-v1 representation of the decision."""

        self.validate()
        return {
            "contract": COMPLETION_DECISION_CONTRACT,
            "schema_version": self.schema_version,
            "decision_id": self.decision_id,
            "scope": {
                "tenant_id": self.tenant_id,
                "workflow_id": self.workflow_id,
                "graph_revision": self.graph_revision,
                "objective_id": self.objective_id,
            },
            "criteria_id": self.criteria_id,
            "criteria_hash": self.criteria_hash,
            "evaluation_authority": _contract_authority_payload(
                self.evaluation_authority
            ),
            "status": self.status.value,
            "accepted_result_ids": list(self.accepted_result_ids),
            "evidence_ids": list(self.evidence_ids),
            "blockers": {
                "missing_requirement_ids": list(self.missing_requirement_ids),
                "unavailable_requirement_ids": list(self.unavailable_requirement_ids),
                "contradictory_requirement_ids": list(
                    self.contradictory_requirement_ids
                ),
                "stale_evidence_ids": list(self.stale_evidence_ids),
                "unverified_evidence_ids": list(self.unverified_evidence_ids),
                "invalid_evidence_ids": list(self.invalid_evidence_ids),
                "missing_result_task_ids": list(self.missing_result_task_ids),
                "partial_task_ids": list(self.partial_task_ids),
                "failed_task_ids": list(self.failed_task_ids),
                "canceled_task_ids": list(self.canceled_task_ids),
            },
            "evaluated_at": _format_datetime(self.evaluated_at),
            "authoritative_event_sequence": self.authoritative_event_sequence,
        }


def _validate_receipt(evidence: EvidenceRecord) -> None:
    if evidence.receipt_status is ReceiptStatus.NOT_REQUIRED:
        if evidence.receipt_id is not None:
            raise OutcomeContractError(
                "not-required receipt status cannot contain receipt_id"
            )
    else:
        _require_identifier("receipt_id", evidence.receipt_id)


def _validate_coverage(result: TaskResult) -> None:
    if type(result.coverage) is not tuple:
        raise OutcomeContractError("coverage must be exact tuple")
    requirement_ids: list[str] = []
    cited_ids: set[str] = set()
    for claim in result.coverage:
        if type(claim) is not CoverageClaim:
            raise OutcomeContractError("coverage must contain CoverageClaim values")
        claim.validate()
        requirement_ids.append(claim.requirement_id)
        cited_ids.update(claim.evidence_ids)
    _require_unique("coverage requirement IDs", requirement_ids)
    if requirement_ids != sorted(requirement_ids):
        raise OutcomeContractError("coverage must use canonical requirement_id order")
    if not cited_ids.issubset(set(result.evidence_ids)):
        raise OutcomeContractError(
            "coverage cannot cite evidence outside the result evidence set"
        )


def _require_same_scope(
    criteria: CompletionCriteria,
    value: EvidenceRecord | TaskResult,
    value_name: str,
) -> None:
    if (
        value.tenant_id != criteria.tenant_id
        or value.workflow_id != criteria.workflow_id
        or value.graph_revision != criteria.graph_revision
    ):
        raise OutcomeContractError(
            f"{value_name} must match criteria tenant, workflow, and revision"
        )


def _require_schema(value: object) -> None:
    if type(value) is not str or value != OUTCOME_SCHEMA_VERSION:
        raise OutcomeContractError("schema_version must match outcome schema 1.0")


def _require_identifier(field_name: str, value: object) -> None:
    if type(value) is not str:
        raise OutcomeContractError(f"{field_name} must be an exact string")
    if not value or value != value.strip():
        raise OutcomeContractError(f"{field_name} must be a non-empty canonical string")


def _require_optional_identifier(field_name: str, value: object) -> None:
    if value is not None:
        _require_identifier(field_name, value)


def _require_digest(field_name: str, value: object) -> None:
    if type(value) is not str or _DIGEST_PATTERN.fullmatch(value) is None:
        raise OutcomeContractError(f"{field_name} must be a lowercase SHA-256 digest")


def _require_enum(field_name: str, value: object, enum_type: type[Enum]) -> None:
    if type(value) is not enum_type:
        raise OutcomeContractError(f"{field_name} must be exact {enum_type.__name__}")


def _require_positive_int(field_name: str, value: object) -> None:
    if type(value) is not int or value < 1:
        raise OutcomeContractError(f"{field_name} must be an exact positive integer")


def _require_nonnegative_int(field_name: str, value: object) -> None:
    if type(value) is not int or value < 0:
        raise OutcomeContractError(
            f"{field_name} must be an exact non-negative integer"
        )


def _require_exact_tuple(field_name: str, value: object) -> None:
    if type(value) is not tuple:
        raise OutcomeContractError(f"{field_name} must be an exact tuple")


def _require_identifier_tuple(
    field_name: str, value: object, *, allow_empty: bool
) -> None:
    _require_exact_tuple(field_name, value)
    if not allow_empty and not value:
        raise OutcomeContractError(f"{field_name} cannot be empty")
    for item in value:
        _require_identifier(f"{field_name} item", item)
    _require_unique(field_name, list(value))
    if list(value) != sorted(value):
        raise OutcomeContractError(f"{field_name} must use canonical order")


def _require_unique(field_name: str, values: list[str]) -> None:
    if len(values) != len(set(values)):
        raise OutcomeContractError(f"{field_name} must be unique")


def _normalize_datetime(field_name: str, value: object) -> datetime:
    if type(value) is not datetime:
        raise OutcomeContractError(f"{field_name} must be exact datetime")
    if type(value.tzinfo) is not timezone or value.utcoffset() is None:
        raise OutcomeContractError(
            f"{field_name} must use immutable built-in fixed-offset timezone"
        )
    return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)


def _format_datetime(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def _format_optional_datetime(value: datetime | None) -> str | None:
    return None if value is None else _format_datetime(value)


def _contract_authority_payload(value: ContractAuthority) -> dict[str, str]:
    if type(value) is not ContractAuthority:
        raise OutcomeContractError("authority must be exact ContractAuthority")
    value.validate()
    return {
        "principal_id": value.principal_id,
        "authority_source": value.authority_source,
        "authority_version": value.authority_version,
    }


def _canonical_payload_digest(value: dict[str, object]) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def evidence_set_digest(value: tuple[EvidenceRecord, ...]) -> str:
    """Hash an exact evidence set independently of caller-provided ordering."""

    _require_exact_tuple("evidence set", value)
    indexed: dict[str, EvidenceRecord] = {}
    for item in value:
        if type(item) is not EvidenceRecord:
            raise OutcomeContractError(
                "evidence set must contain EvidenceRecord values"
            )
        item.validate()
        if item.evidence_id in indexed:
            raise OutcomeContractError("evidence set IDs must be unique")
        indexed[item.evidence_id] = item
    payload: dict[str, object] = {
        "contract": "workflow.evidence-set",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "members": [
            {
                "evidence_id": evidence_id,
                "evidence_digest": _canonical_payload_digest(
                    indexed[evidence_id].canonical_payload()
                ),
            }
            for evidence_id in sorted(indexed)
        ],
    }
    return _canonical_payload_digest(payload)


__all__ = [
    "AcceptedTaskResultAttestation",
    "AuthoritativeTaskDefinition",
    "COMPLETION_CRITERIA_CONTRACT",
    "COMPLETION_DECISION_CONTRACT",
    "EVIDENCE_CONTRACT",
    "OUTCOME_SCHEMA_VERSION",
    "RESULT_CONTRACT",
    "CompletionCriteria",
    "CompletionAuthoritySnapshot",
    "CompletionDecision",
    "CompletionDisplayStatus",
    "CompletionStatus",
    "ContractAuthority",
    "CoverageClaim",
    "CoverageStatus",
    "EvidenceAvailability",
    "EvidenceProvenance",
    "EvidenceRecord",
    "EvidenceRequirement",
    "OutcomeContractError",
    "ReceiptStatus",
    "ResultOutcome",
    "ResultValidationAuthority",
    "ResultValidationStatus",
    "TaskResult",
    "evidence_set_digest",
]
