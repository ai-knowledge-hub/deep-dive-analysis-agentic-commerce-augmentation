"""Authority-bound evaluation of workflow evidence and task results."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from domain.workflow.outcome_serialization import (
    completion_criteria_digest,
    task_result_digest,
)
from domain.workflow.outcomes import (
    OUTCOME_SCHEMA_VERSION,
    AcceptedTaskResultAttestation,
    AuthoritativeTaskDefinition,
    CompletionAuthoritySnapshot,
    CompletionCriteria,
    CompletionDecision,
    CompletionStatus,
    CoverageStatus,
    EvidenceAvailability,
    EvidenceRecord,
    EvidenceRequirement,
    OutcomeContractError,
    ReceiptStatus,
    ResultOutcome,
    ResultValidationStatus,
    TaskResult,
    evidence_set_digest,
)


def evaluate_completion(
    *,
    decision_id: str,
    criteria: CompletionCriteria,
    authority_snapshot: CompletionAuthoritySnapshot,
    results: tuple[TaskResult, ...],
    evidence: tuple[EvidenceRecord, ...],
    evaluated_at: datetime,
    authoritative_event_sequence: int,
) -> CompletionDecision:
    """Evaluate submissions against a host-read authority snapshot."""

    if type(criteria) is not CompletionCriteria:
        raise OutcomeContractError("criteria must be CompletionCriteria")
    criteria.validate()
    if type(authority_snapshot) is not CompletionAuthoritySnapshot:
        raise OutcomeContractError(
            "authority_snapshot must be CompletionAuthoritySnapshot"
        )
    authority_snapshot.validate()
    _require_authoritative_criteria(criteria, authority_snapshot)
    evaluated_at = _exact_datetime("evaluated_at", evaluated_at)
    if criteria.created_at > evaluated_at:
        raise OutcomeContractError("criteria cannot be published after evaluation")
    _exact_tuple("results", results)
    _exact_tuple("evidence", evidence)

    evidence_by_id = _index_evidence(criteria, evidence, evaluated_at)
    result_by_task, accepted_results = _index_results(
        criteria, authority_snapshot, results, evidence_by_id, evaluated_at
    )
    missing_tasks, partial_tasks, failed_tasks, canceled_tasks = _classify_tasks(
        criteria, result_by_task
    )
    blockers = _evaluate_coverage(
        criteria, result_by_task, evidence_by_id, evaluated_at
    )
    missing, unavailable, contradictory, stale, unverified, invalid, used = blockers
    incomplete = any(
        (
            missing_tasks,
            partial_tasks,
            failed_tasks,
            canceled_tasks,
            missing,
            unavailable,
            contradictory,
            stale,
            unverified,
            invalid,
        )
    )
    return CompletionDecision(
        decision_id=decision_id,
        schema_version=OUTCOME_SCHEMA_VERSION,
        tenant_id=criteria.tenant_id,
        workflow_id=criteria.workflow_id,
        graph_revision=criteria.graph_revision,
        objective_id=criteria.objective_id,
        criteria_id=criteria.criteria_id,
        criteria_hash=authority_snapshot.criteria_hash,
        evaluation_authority=authority_snapshot.evaluation_authority,
        status=(
            CompletionStatus.INCOMPLETE if incomplete else CompletionStatus.COMPLETE
        ),
        accepted_result_ids=tuple(sorted(item.result_id for item in accepted_results)),
        evidence_ids=tuple(sorted(used)),
        missing_requirement_ids=tuple(sorted(missing)),
        unavailable_requirement_ids=tuple(sorted(unavailable)),
        contradictory_requirement_ids=tuple(sorted(contradictory)),
        stale_evidence_ids=tuple(sorted(stale)),
        unverified_evidence_ids=tuple(sorted(unverified)),
        invalid_evidence_ids=tuple(sorted(invalid)),
        missing_result_task_ids=tuple(sorted(missing_tasks)),
        partial_task_ids=tuple(sorted(partial_tasks)),
        failed_task_ids=tuple(sorted(failed_tasks)),
        canceled_task_ids=tuple(sorted(canceled_tasks)),
        evaluated_at=evaluated_at,
        authoritative_event_sequence=authoritative_event_sequence,
    )


def _require_authoritative_criteria(
    criteria: CompletionCriteria, authority: CompletionAuthoritySnapshot
) -> None:
    actual_scope = (
        criteria.tenant_id,
        criteria.workflow_id,
        criteria.graph_revision,
        criteria.objective_id,
        criteria.criteria_id,
    )
    expected_scope = (
        authority.tenant_id,
        authority.workflow_id,
        authority.graph_revision,
        authority.objective_id,
        authority.criteria_id,
    )
    if actual_scope != expected_scope:
        raise OutcomeContractError("criteria scope must match host authority snapshot")
    if completion_criteria_digest(criteria) != authority.criteria_hash:
        raise OutcomeContractError("criteria must match host-attested criteria hash")
    if criteria.authority_hash != authority.criteria_authority_hash:
        raise OutcomeContractError("criteria authority hash is not authoritative")
    if criteria.publishing_authority != authority.publishing_authority:
        raise OutcomeContractError("criteria publishing authority is not authoritative")
    bound_tasks = tuple(item.task_id for item in authority.task_definitions)
    if bound_tasks != criteria.required_task_ids:
        raise OutcomeContractError(
            "authoritative task definitions must equal the required task set"
        )


def _index_evidence(
    criteria: CompletionCriteria,
    evidence: tuple[EvidenceRecord, ...],
    evaluated_at: datetime,
) -> dict[str, EvidenceRecord]:
    indexed: dict[str, EvidenceRecord] = {}
    observation_ids: set[str] = set()
    receipt_identities: set[tuple[str, str, str, str]] = set()
    for item in evidence:
        if type(item) is not EvidenceRecord:
            raise OutcomeContractError("evidence must contain EvidenceRecord values")
        item.validate()
        _same_scope(criteria, item, "evidence")
        if item.recorded_at > evaluated_at:
            raise OutcomeContractError("evidence cannot be recorded after evaluation")
        if item.evidence_id in indexed:
            raise OutcomeContractError("evidence IDs must be unique")
        if item.receipt_id is not None:
            receipt_identity = (
                item.provenance.source_type,
                item.provenance.source_id,
                item.provenance.source_version,
                item.receipt_id,
            )
            if receipt_identity in receipt_identities:
                raise OutcomeContractError(
                    "a source-scoped receipt can identify only one evidence observation"
                )
            receipt_identities.add(receipt_identity)
        observation_id = _observation_identity(item)
        if observation_id in observation_ids:
            raise OutcomeContractError(
                "evidence records must represent distinct observations"
            )
        observation_ids.add(observation_id)
        indexed[item.evidence_id] = item
    return indexed


def _observation_identity(item: EvidenceRecord) -> str:
    """Identity of source observation, deliberately excluding evidence_id."""

    if item.receipt_id is not None:
        payload: dict[str, object] = {
            "source_type": item.provenance.source_type,
            "source_id": item.provenance.source_id,
            "source_version": item.provenance.source_version,
            "receipt_id": item.receipt_id,
        }
    else:
        payload = {
            "scope": [item.tenant_id, item.workflow_id, item.graph_revision],
            "task": [item.task_id, item.attempt_id, item.action_id],
            "source": [
                item.provenance.source_type,
                item.provenance.source_id,
                item.provenance.source_version,
                item.provenance.source_contract_hash,
            ],
            "content_hash": item.content_hash,
            "observed_at": None
            if item.observed_at is None
            else item.observed_at.isoformat(timespec="microseconds"),
            "failure_code": item.failure_code,
        }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _index_results(
    criteria: CompletionCriteria,
    authority: CompletionAuthoritySnapshot,
    results: tuple[TaskResult, ...],
    evidence_by_id: dict[str, EvidenceRecord],
    evaluated_at: datetime,
) -> tuple[dict[str, TaskResult], list[TaskResult]]:
    indexed: dict[str, TaskResult] = {}
    accepted: list[TaskResult] = []
    seen_result_ids: set[str] = set()
    definitions = {item.task_id: item for item in authority.task_definitions}
    attestations = {
        item.task_id: item for item in authority.accepted_result_attestations
    }
    for result in results:
        if type(result) is not TaskResult:
            raise OutcomeContractError("results must contain TaskResult values")
        result.validate()
        _same_scope(criteria, result, "result")
        if result.result_id in seen_result_ids:
            raise OutcomeContractError("result IDs must be unique")
        seen_result_ids.add(result.result_id)
        bound_evidence = _resolve_result_evidence(result, evidence_by_id)
        if result.evidence_digest != evidence_set_digest(bound_evidence):
            raise OutcomeContractError(
                "result evidence_digest must match exact evidence contents"
            )
        if result.created_at > evaluated_at or (
            result.validated_at is not None and result.validated_at > evaluated_at
        ):
            raise OutcomeContractError(
                "result cannot be created or validated after evaluation"
            )
        if result.validation_status is not ResultValidationStatus.ACCEPTED:
            continue
        if result.task_id not in criteria.required_task_ids:
            continue
        if result.task_id in indexed:
            raise OutcomeContractError(
                "completion input cannot contain multiple accepted results per task"
            )
        attestation = attestations.get(result.task_id)
        if attestation is None:
            raise OutcomeContractError(
                "accepted result requires a host result attestation"
            )
        _require_authoritative_result(result, definitions[result.task_id], attestation)
        indexed[result.task_id] = result
        accepted.append(result)
    return indexed, accepted


def _resolve_result_evidence(
    result: TaskResult, evidence_by_id: dict[str, EvidenceRecord]
) -> tuple[EvidenceRecord, ...]:
    resolved: list[EvidenceRecord] = []
    for evidence_id in result.evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None:
            raise OutcomeContractError(
                "result evidence set must resolve before completion evaluation"
            )
        if item.task_id != result.task_id or item.attempt_id != result.attempt_id:
            raise OutcomeContractError(
                "every result evidence member must belong to the exact task attempt"
            )
        resolved.append(item)
    return tuple(resolved)


def _require_authoritative_result(
    result: TaskResult,
    definition: AuthoritativeTaskDefinition,
    attestation: AcceptedTaskResultAttestation,
) -> None:
    actual = (
        result.task_id,
        result.task_input_hash,
        result.result_schema_id,
        result.result_schema_version,
        result.result_schema_hash,
    )
    expected = (
        definition.task_id,
        definition.task_input_hash,
        definition.result_schema_id,
        definition.result_schema_version,
        definition.result_schema_hash,
    )
    if actual != expected:
        raise OutcomeContractError(
            "accepted result must match the host task definition"
        )
    attested = (
        result.task_id,
        result.attempt_id,
        result.assignment_id,
        result.validation_authority,
        task_result_digest(result),
    )
    expected_attestation = (
        attestation.task_id,
        attestation.attempt_id,
        attestation.assignment_id,
        attestation.validation_authority,
        attestation.accepted_result_hash,
    )
    if attested != expected_attestation:
        raise OutcomeContractError(
            "accepted result must match the host coordinator attestation"
        )


def _classify_tasks(
    criteria: CompletionCriteria, result_by_task: dict[str, TaskResult]
) -> tuple[set[str], set[str], set[str], set[str]]:
    outcomes = (set(), set(), set(), set())
    missing, partial, failed, canceled = outcomes
    for task_id in criteria.required_task_ids:
        result = result_by_task.get(task_id)
        if result is None:
            missing.add(task_id)
        elif result.outcome is ResultOutcome.PARTIAL:
            partial.add(task_id)
        elif result.outcome is ResultOutcome.FAILED:
            failed.add(task_id)
        elif result.outcome is ResultOutcome.CANCELED:
            canceled.add(task_id)
    return outcomes


def _evaluate_coverage(
    criteria: CompletionCriteria,
    result_by_task: dict[str, TaskResult],
    evidence_by_id: dict[str, EvidenceRecord],
    evaluated_at: datetime,
) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str], set[str]]:
    aggregate = tuple(set() for _ in range(7))
    for requirement in criteria.evidence_requirements:
        values = _evaluate_requirement(
            requirement,
            result_by_task.get(requirement.task_id),
            evidence_by_id,
            evaluated_at,
        )
        for target, additions in zip(aggregate, values, strict=True):
            target.update(additions)
    return aggregate


def _evaluate_requirement(
    requirement: EvidenceRequirement,
    result: TaskResult | None,
    evidence_by_id: dict[str, EvidenceRecord],
    evaluated_at: datetime,
) -> tuple[set[str], set[str], set[str], set[str], set[str], set[str], set[str]]:
    outcome = tuple(set() for _ in range(7))
    missing, unavailable, contradictory, stale, unverified, invalid, used = outcome
    if result is None:
        missing.add(requirement.requirement_id)
        return outcome
    claim = next(
        (
            item
            for item in result.coverage
            if item.requirement_id == requirement.requirement_id
        ),
        None,
    )
    if claim is None or claim.status is CoverageStatus.MISSING:
        missing.add(requirement.requirement_id)
        return outcome
    if claim.status is CoverageStatus.UNAVAILABLE:
        unavailable.add(requirement.requirement_id)
        return outcome
    if claim.status is CoverageStatus.CONTRADICTORY:
        contradictory.add(requirement.requirement_id)
        return outcome
    valid_items = 0
    for evidence_id in claim.evidence_ids:
        item = evidence_by_id.get(evidence_id)
        if item is None:
            missing.add(requirement.requirement_id)
        elif item.availability is EvidenceAvailability.UNAVAILABLE:
            unavailable.add(requirement.requirement_id)
        elif item.provenance.source_type not in requirement.allowed_source_types:
            invalid.add(evidence_id)
        elif _stale(requirement, item, evaluated_at):
            stale.add(evidence_id)
        elif _invalid_receipt(requirement, item):
            unverified.add(evidence_id)
        else:
            valid_items += 1
            used.add(evidence_id)
    if valid_items < requirement.min_items and not any(
        (stale, unverified, invalid, unavailable)
    ):
        missing.add(requirement.requirement_id)
    return outcome


def _stale(
    requirement: EvidenceRequirement, item: EvidenceRecord, evaluated_at: datetime
) -> bool:
    return not item.is_fresh_at(evaluated_at) or bool(
        item.observed_at is not None
        and (evaluated_at - item.observed_at).total_seconds()
        > requirement.max_age_seconds
    )


def _invalid_receipt(requirement: EvidenceRequirement, item: EvidenceRecord) -> bool:
    return item.receipt_status not in {
        ReceiptStatus.NOT_REQUIRED,
        ReceiptStatus.VERIFIED,
    } or (
        requirement.require_verified_receipt
        and item.receipt_status is not ReceiptStatus.VERIFIED
    )


def _same_scope(
    criteria: CompletionCriteria, value: EvidenceRecord | TaskResult, name: str
) -> None:
    if (
        value.tenant_id,
        value.workflow_id,
        value.graph_revision,
    ) != (criteria.tenant_id, criteria.workflow_id, criteria.graph_revision):
        raise OutcomeContractError(
            f"{name} must match criteria tenant, workflow, and revision"
        )


def _exact_tuple(name: str, value: object) -> None:
    if type(value) is not tuple:
        raise OutcomeContractError(f"{name} must be an exact tuple")


def _exact_datetime(name: str, value: object) -> datetime:
    if type(value) is not datetime or type(value.tzinfo) is not timezone:
        raise OutcomeContractError(
            f"{name} must use immutable built-in fixed-offset timezone"
        )
    return datetime.fromtimestamp(value.timestamp(), tz=timezone.utc)


__all__ = ["evaluate_completion"]
