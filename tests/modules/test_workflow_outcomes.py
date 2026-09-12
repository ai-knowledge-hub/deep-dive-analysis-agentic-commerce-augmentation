from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta, timezone, tzinfo

import pytest

from domain.workflow import (
    OUTCOME_SCHEMA_VERSION,
    AcceptedTaskResultAttestation,
    AuthoritativeTaskDefinition,
    CompletionAuthoritySnapshot,
    CompletionCriteria,
    CompletionDisplayStatus,
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
    completion_criteria_digest,
    completion_criteria_from_payload,
    completion_criteria_payload,
    completion_authority_snapshot_digest,
    completion_authority_snapshot_from_payload,
    completion_authority_snapshot_payload,
    completion_decision_digest,
    completion_decision_from_payload,
    completion_decision_payload,
    evidence_digest,
    evidence_from_payload,
    evidence_payload,
    evidence_set_digest,
    evaluate_completion,
    project_completion,
    task_result_digest,
    task_result_from_payload,
    task_result_payload,
)


NOW = datetime(2026, 9, 8, 8, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def _provenance(*, source_type: str = "provider_api") -> EvidenceProvenance:
    return EvidenceProvenance(
        source_type=source_type,
        source_id="validation-job:job-1",
        source_version="1",
        source_contract_hash=HASH_B,
        producer_principal_id="internal-agent:validator",
        capability_id="request_synthetic_validation",
        tool_id="validation.request_synthetic",
    )


def _evidence(**overrides: object) -> EvidenceRecord:
    values: dict[str, object] = {
        "evidence_id": "evidence-1",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "tenant_id": "tenant-a",
        "workflow_id": "workflow-a",
        "graph_revision": 1,
        "task_id": "task-a",
        "attempt_id": "attempt-a1",
        "action_id": "action-a",
        "availability": EvidenceAvailability.AVAILABLE,
        "content_hash": HASH_A,
        "provenance": _provenance(),
        "receipt_status": ReceiptStatus.VERIFIED,
        "receipt_id": "validation-job:job-1",
        "observed_at": NOW,
        "valid_until": NOW + timedelta(hours=2),
        "recorded_at": NOW + timedelta(seconds=1),
        "failure_code": None,
    }
    values.update(overrides)
    return EvidenceRecord(**values)  # type: ignore[arg-type]


def _requirement(**overrides: object) -> EvidenceRequirement:
    values: dict[str, object] = {
        "requirement_id": "requirement-a",
        "task_id": "task-a",
        "min_items": 1,
        "max_age_seconds": 3600,
        "require_verified_receipt": True,
        "allowed_source_types": ("provider_api",),
    }
    values.update(overrides)
    return EvidenceRequirement(**values)  # type: ignore[arg-type]


def _contract_authority(
    *, principal_id: str = "policy:completion-owner"
) -> ContractAuthority:
    return ContractAuthority(
        principal_id=principal_id,
        authority_source="workflow-policy",
        authority_version="1",
    )


def _criteria(**overrides: object) -> CompletionCriteria:
    values: dict[str, object] = {
        "criteria_id": "criteria-a",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "tenant_id": "tenant-a",
        "workflow_id": "workflow-a",
        "graph_revision": 1,
        "objective_id": "objective-a",
        "criteria_version": "1",
        "publishing_authority": _contract_authority(),
        "authority_hash": HASH_B,
        "required_task_ids": ("task-a",),
        "evidence_requirements": (_requirement(),),
        "created_at": NOW - timedelta(minutes=1),
    }
    values.update(overrides)
    return CompletionCriteria(**values)  # type: ignore[arg-type]


def _authority() -> ResultValidationAuthority:
    return ResultValidationAuthority(
        principal_id="coordinator:workflow-a",
        authority_source="workflow-runtime",
        authority_version="1",
    )


def _result(**overrides: object) -> TaskResult:
    values: dict[str, object] = {
        "result_id": "result-a",
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "tenant_id": "tenant-a",
        "workflow_id": "workflow-a",
        "graph_revision": 1,
        "task_id": "task-a",
        "attempt_id": "attempt-a1",
        "assignment_id": None,
        "task_input_hash": HASH_B,
        "result_schema_id": "validation-result",
        "result_schema_version": "1",
        "result_schema_hash": "c" * 64,
        "producer_principal_id": "internal-agent:validator",
        "outcome": ResultOutcome.SUCCEEDED,
        "payload_hash": HASH_A,
        "evidence_ids": ("evidence-1",),
        "evidence_digest": evidence_set_digest((_evidence(),)),
        "coverage": (
            CoverageClaim(
                requirement_id="requirement-a",
                status=CoverageStatus.SATISFIED,
                evidence_ids=("evidence-1",),
            ),
        ),
        "validation_status": ResultValidationStatus.ACCEPTED,
        "validation_authority": _authority(),
        "validated_at": NOW + timedelta(seconds=2),
        "created_at": NOW + timedelta(seconds=1),
        "error_code": None,
    }
    values.update(overrides)
    if "evidence_digest" not in overrides and values["evidence_ids"] == ():
        values["evidence_digest"] = evidence_set_digest(())
    return TaskResult(**values)  # type: ignore[arg-type]


def _authority_snapshot(
    criteria: CompletionCriteria,
    results: tuple[TaskResult, ...],
    **overrides: object,
) -> CompletionAuthoritySnapshot:
    accepted_by_task: dict[str, TaskResult] = {}
    for item in results:
        accepted_by_task.setdefault(item.task_id, item)
    definitions = tuple(
        AuthoritativeTaskDefinition(
            task_id=task_id,
            task_input_hash=(
                accepted_by_task[task_id].task_input_hash
                if task_id in accepted_by_task
                else HASH_B
            ),
            result_schema_id=(
                accepted_by_task[task_id].result_schema_id
                if task_id in accepted_by_task
                else "validation-result"
            ),
            result_schema_version=(
                accepted_by_task[task_id].result_schema_version
                if task_id in accepted_by_task
                else "1"
            ),
            result_schema_hash=(
                accepted_by_task[task_id].result_schema_hash
                if task_id in accepted_by_task
                else "c" * 64
            ),
        )
        for task_id in criteria.required_task_ids
    )
    attestations = tuple(
        AcceptedTaskResultAttestation(
            task_id=result.task_id,
            attempt_id=result.attempt_id,
            assignment_id=result.assignment_id,
            validation_authority=result.validation_authority,
            accepted_result_hash=task_result_digest(result),
        )
        for result in accepted_by_task.values()
        if result.task_id in criteria.required_task_ids
        and result.validation_status is ResultValidationStatus.ACCEPTED
    )
    values: dict[str, object] = {
        "tenant_id": criteria.tenant_id,
        "workflow_id": criteria.workflow_id,
        "graph_revision": criteria.graph_revision,
        "objective_id": criteria.objective_id,
        "criteria_id": criteria.criteria_id,
        "criteria_hash": completion_criteria_digest(criteria),
        "criteria_authority_hash": criteria.authority_hash,
        "publishing_authority": criteria.publishing_authority,
        "evaluation_authority": _contract_authority(
            principal_id="runtime:completion-evaluator"
        ),
        "task_definitions": definitions,
        "accepted_result_attestations": attestations,
    }
    values.update(overrides)
    return CompletionAuthoritySnapshot(**values)  # type: ignore[arg-type]


def _decision(**overrides: object):
    criteria = overrides.pop("criteria", _criteria())
    evidence_values = overrides.pop("evidence", (_evidence(),))
    result_values = overrides.pop("results", None)
    if result_values is None:
        result_values = (_result(evidence_digest=evidence_set_digest(evidence_values)),)
    authority_snapshot = overrides.pop(
        "authority_snapshot", _authority_snapshot(criteria, result_values)
    )
    return evaluate_completion(
        decision_id="decision-a",
        criteria=criteria,
        authority_snapshot=authority_snapshot,
        results=result_values,
        evidence=evidence_values,
        evaluated_at=overrides.pop("evaluated_at", NOW + timedelta(minutes=10)),
        authoritative_event_sequence=overrides.pop("authoritative_event_sequence", 14),
        **overrides,
    )


def test_complete_requires_exact_accepted_result_and_fresh_verified_evidence():
    decision = _decision()

    assert decision.status is CompletionStatus.COMPLETE
    assert decision.accepted_result_ids == ("result-a",)
    assert decision.evidence_ids == ("evidence-1",)
    assert not decision.missing_requirement_ids


def test_successful_tool_output_cannot_imply_completion_without_accepted_result():
    criteria = _criteria()
    authority = _authority_snapshot(criteria, ())

    decision = _decision(criteria=criteria, results=(), authority_snapshot=authority)

    assert authority.accepted_result_attestations == ()
    assert decision.status is CompletionStatus.INCOMPLETE
    assert decision.missing_result_task_ids == ("task-a",)
    assert decision.missing_requirement_ids == ("requirement-a",)


def test_result_cannot_self_select_a_smaller_completion_contract():
    criteria = _criteria(
        evidence_requirements=(
            _requirement(),
            _requirement(requirement_id="requirement-b"),
        )
    )

    decision = _decision(criteria=criteria)

    assert decision.status is CompletionStatus.INCOMPLETE
    assert decision.missing_requirement_ids == ("requirement-b",)


@pytest.mark.parametrize(
    ("evidence", "blocker_field"),
    [
        (
            _evidence(
                observed_at=NOW - timedelta(hours=2),
                valid_until=NOW + timedelta(hours=1),
            ),
            "stale_evidence_ids",
        ),
        (
            _evidence(
                receipt_status=ReceiptStatus.PENDING,
                receipt_id="validation-job:job-1",
            ),
            "unverified_evidence_ids",
        ),
    ],
)
def test_stale_or_unverified_evidence_blocks_completion(evidence, blocker_field):
    decision = _decision(evidence=(evidence,))

    assert decision.status is CompletionStatus.INCOMPLETE
    assert getattr(decision, blocker_field) == ("evidence-1",)
    assert not decision.missing_requirement_ids


@pytest.mark.parametrize(
    "evidence",
    [
        _evidence(tenant_id="tenant-b"),
        _evidence(workflow_id="workflow-b"),
        _evidence(graph_revision=2),
    ],
)
def test_evidence_scope_substitution_fails_closed(evidence):
    with pytest.raises(OutcomeContractError, match="must match criteria"):
        _decision(evidence=(evidence,))


def test_valid_evidence_from_another_attempt_cannot_fulfil_result():
    with pytest.raises(OutcomeContractError, match="exact task attempt"):
        _decision(evidence=(_evidence(attempt_id="attempt-a2"),))


def test_same_evidence_id_cannot_hide_content_substitution():
    with pytest.raises(OutcomeContractError, match="exact evidence contents"):
        _decision(
            results=(_result(),),
            evidence=(_evidence(content_hash="d" * 64),),
        )


def test_multiple_accepted_results_for_one_task_are_ambiguous():
    with pytest.raises(OutcomeContractError, match="multiple accepted results"):
        _decision(results=(_result(), _result(result_id="result-b")))


def test_partial_result_must_expose_unsatisfied_coverage():
    with pytest.raises(OutcomeContractError, match="partial result"):
        _result(outcome=ResultOutcome.PARTIAL)


def test_succeeded_result_cannot_launder_missing_coverage():
    with pytest.raises(OutcomeContractError, match="succeeded result"):
        _result(
            coverage=(
                CoverageClaim(
                    requirement_id="requirement-a",
                    status=CoverageStatus.MISSING,
                    evidence_ids=(),
                ),
            )
        )


@pytest.mark.parametrize(
    ("result", "task_blocker"),
    [
        (
            _result(
                outcome=ResultOutcome.PARTIAL,
                evidence_ids=(),
                coverage=(
                    CoverageClaim(
                        requirement_id="requirement-a",
                        status=CoverageStatus.MISSING,
                        evidence_ids=(),
                    ),
                ),
            ),
            "partial_task_ids",
        ),
        (
            _result(
                outcome=ResultOutcome.FAILED,
                payload_hash=None,
                evidence_ids=(),
                coverage=(),
                error_code="provider_failed",
            ),
            "failed_task_ids",
        ),
        (
            _result(
                outcome=ResultOutcome.CANCELED,
                payload_hash=None,
                evidence_ids=(),
                coverage=(),
                error_code="operator_canceled",
            ),
            "canceled_task_ids",
        ),
    ],
)
def test_non_successful_accepted_results_preserve_their_task_outcome(
    result, task_blocker
):
    decision = _decision(results=(result,))

    assert decision.status is CompletionStatus.INCOMPLETE
    assert getattr(decision, task_blocker) == ("task-a",)


def test_rejected_result_is_not_completion_evidence():
    decision = _decision(
        results=(_result(validation_status=ResultValidationStatus.REJECTED),)
    )

    assert decision.missing_result_task_ids == ("task-a",)
    assert decision.status is CompletionStatus.INCOMPLETE


@pytest.mark.parametrize(
    ("coverage_status", "blocker_field"),
    [
        (CoverageStatus.UNAVAILABLE, "unavailable_requirement_ids"),
        (CoverageStatus.CONTRADICTORY, "contradictory_requirement_ids"),
    ],
)
def test_coverage_failure_reason_is_preserved(coverage_status, blocker_field):
    result = _result(
        outcome=ResultOutcome.PARTIAL,
        coverage=(
            CoverageClaim(
                requirement_id="requirement-a",
                status=coverage_status,
                evidence_ids=("evidence-1",),
            ),
        ),
    )

    decision = _decision(results=(result,))

    assert getattr(decision, blocker_field) == ("requirement-a",)
    assert decision.partial_task_ids == ("task-a",)


def test_wrong_evidence_source_is_explicitly_invalid():
    decision = _decision(
        evidence=(_evidence(provenance=_provenance(source_type="model_claim")),)
    )

    assert decision.status is CompletionStatus.INCOMPLETE
    assert decision.invalid_evidence_ids == ("evidence-1",)


def test_unavailable_evidence_is_explicit_and_cannot_claim_content():
    unavailable = _evidence(
        availability=EvidenceAvailability.UNAVAILABLE,
        content_hash=None,
        receipt_status=ReceiptStatus.NOT_REQUIRED,
        receipt_id=None,
        observed_at=None,
        valid_until=None,
        failure_code="provider_unavailable",
    )
    assert not unavailable.is_fresh_at(NOW)

    with pytest.raises(OutcomeContractError, match="cannot contain observed content"):
        _evidence(
            availability=EvidenceAvailability.UNAVAILABLE,
            failure_code="provider_unavailable",
        )


def test_lagging_projection_must_report_stale_not_complete():
    decision = _decision()
    projection = project_completion(
        decision,
        decision_hash=completion_decision_digest(decision),
        authoritative_stream_sequence=14,
        projected_event_sequence=13,
        projected_at=NOW + timedelta(minutes=11),
    )

    assert projection.display_status is CompletionDisplayStatus.STALE
    assert projection.projection_lag == 1


def test_current_projection_reports_authoritative_completion():
    decision = _decision()
    projection = project_completion(
        decision,
        decision_hash=completion_decision_digest(decision),
        authoritative_stream_sequence=14,
        projected_event_sequence=14,
        projected_at=NOW + timedelta(minutes=11),
    )

    assert projection.display_status is CompletionDisplayStatus.COMPLETE
    assert projection.projection_lag == 0


@pytest.mark.parametrize(
    ("value", "payload", "parser", "digest"),
    [
        (_evidence(), evidence_payload, evidence_from_payload, evidence_digest),
        (
            _criteria(),
            completion_criteria_payload,
            completion_criteria_from_payload,
            completion_criteria_digest,
        ),
        (_result(), task_result_payload, task_result_from_payload, task_result_digest),
        (
            _decision(),
            completion_decision_payload,
            completion_decision_from_payload,
            completion_decision_digest,
        ),
        (
            _authority_snapshot(_criteria(), (_result(),)),
            completion_authority_snapshot_payload,
            completion_authority_snapshot_from_payload,
            completion_authority_snapshot_digest,
        ),
    ],
)
def test_schema_v1_round_trip_and_digest_are_stable(value, payload, parser, digest):
    encoded = payload(value)
    parsed = parser(deepcopy(encoded))

    assert parsed == value
    assert digest(parsed) == digest(value)


@pytest.mark.parametrize(
    ("payload_factory", "parser"),
    [
        (lambda: evidence_payload(_evidence()), evidence_from_payload),
        (
            lambda: completion_criteria_payload(_criteria()),
            completion_criteria_from_payload,
        ),
        (lambda: task_result_payload(_result()), task_result_from_payload),
        (
            lambda: completion_decision_payload(_decision()),
            completion_decision_from_payload,
        ),
        (
            lambda: completion_authority_snapshot_payload(
                _authority_snapshot(_criteria(), (_result(),))
            ),
            completion_authority_snapshot_from_payload,
        ),
    ],
)
def test_schema_v1_rejects_unknown_or_omitted_fields(payload_factory, parser):
    unknown = payload_factory()
    unknown["unexpected"] = True
    with pytest.raises(OutcomeContractError, match="fields must match schema v1"):
        parser(unknown)

    omitted = payload_factory()
    omitted.pop("schema_version")
    with pytest.raises(OutcomeContractError, match="fields must match schema v1"):
        parser(omitted)


class LyingString(str):
    def strip(self, chars=None):  # noqa: ANN001
        return "canonical"


class LyingInteger(int):
    def __lt__(self, other):  # noqa: ANN001
        return False


class MutableTimezone(tzinfo):
    offset = 0

    def utcoffset(self, dt):  # noqa: ANN001
        return timedelta(hours=self.offset)

    def dst(self, dt):  # noqa: ANN001
        return timedelta(0)


@pytest.mark.parametrize(
    "constructor",
    [
        lambda: _evidence(evidence_id=LyingString(" ")),
        lambda: _evidence(graph_revision=LyingInteger(-1)),
        lambda: _criteria(required_task_ids=(LyingString("task-a"),)),
        lambda: _result(evidence_ids=(LyingString("evidence-1"),)),
        lambda: _evidence(recorded_at=datetime(2026, 9, 8, tzinfo=MutableTimezone())),
    ],
)
def test_closed_object_graph_rejects_hostile_primitive_subclasses(constructor):
    with pytest.raises(OutcomeContractError):
        constructor()


def test_mapping_parser_rejects_hostile_leaf_types():
    payload = completion_criteria_payload(_criteria())
    payload["scope"]["graph_revision"] = LyingInteger(-1)

    with pytest.raises(OutcomeContractError, match="exact positive integer"):
        completion_criteria_from_payload(payload)


def test_digests_change_when_authority_or_evidence_changes():
    base_criteria = _criteria()
    other_criteria = _criteria(authority_hash="c" * 64)
    base_evidence = _evidence()
    other_evidence = _evidence(content_hash="d" * 64)

    assert completion_criteria_digest(base_criteria) != completion_criteria_digest(
        other_criteria
    )
    assert evidence_digest(base_evidence) != evidence_digest(other_evidence)
    assert task_result_digest(_result()) != task_result_digest(
        _result(result_schema_hash="e" * 64)
    )


def test_evaluator_rejects_a_criteria_not_attested_by_host_authority():
    criteria = _criteria()
    result = _result()
    with pytest.raises(OutcomeContractError, match="host-attested criteria hash"):
        evaluate_completion(
            decision_id="decision-a",
            criteria=criteria,
            authority_snapshot=_authority_snapshot(
                criteria, (result,), criteria_hash="f" * 64
            ),
            results=(result,),
            evidence=(_evidence(),),
            evaluated_at=NOW + timedelta(minutes=10),
            authoritative_event_sequence=14,
        )


def test_result_producer_cannot_validate_its_own_result():
    with pytest.raises(OutcomeContractError, match="cannot validate its own"):
        _result(
            validation_authority=ResultValidationAuthority(
                principal_id="internal-agent:validator",
                authority_source="workflow-runtime",
                authority_version="1",
            )
        )


def test_future_evidence_cannot_be_used_by_an_earlier_decision():
    with pytest.raises(OutcomeContractError, match="recorded after evaluation"):
        _decision(evidence=(_evidence(recorded_at=NOW + timedelta(hours=1)),))


@pytest.mark.parametrize(
    ("evidence_value", "result_times", "message"),
    [
        (
            _evidence(
                observed_at=NOW + timedelta(minutes=10),
                recorded_at=NOW + timedelta(minutes=11),
            ),
            {
                "created_at": NOW + timedelta(minutes=3),
                "validated_at": NOW + timedelta(minutes=12),
            },
            "observed after result creation",
        ),
        (
            _evidence(recorded_at=NOW + timedelta(minutes=10)),
            {
                "created_at": NOW + timedelta(minutes=3),
                "validated_at": NOW + timedelta(minutes=4),
            },
            "recorded after result validation",
        ),
    ],
)
def test_result_cannot_cite_evidence_outside_its_causal_window(
    evidence_value, result_times, message
):
    result_value = _result(
        evidence_digest=evidence_set_digest((evidence_value,)),
        **result_times,
    )

    with pytest.raises(OutcomeContractError, match=message):
        _decision(
            results=(result_value,),
            evidence=(evidence_value,),
            evaluated_at=NOW + timedelta(minutes=20),
        )


def test_result_evidence_causal_boundaries_are_inclusive():
    evidence_value = _evidence(
        observed_at=NOW + timedelta(minutes=3),
        recorded_at=NOW + timedelta(minutes=4),
    )
    result_value = _result(
        evidence_digest=evidence_set_digest((evidence_value,)),
        created_at=evidence_value.observed_at,
        validated_at=evidence_value.recorded_at,
    )

    decision = _decision(results=(result_value,), evidence=(evidence_value,))

    assert decision.status is CompletionStatus.COMPLETE


def test_projection_rejects_a_self_certified_decision_hash():
    with pytest.raises(OutcomeContractError, match="exact completion decision"):
        project_completion(
            _decision(),
            decision_hash="f" * 64,
            authoritative_stream_sequence=14,
            projected_event_sequence=14,
            projected_at=NOW + timedelta(minutes=11),
        )


def test_coordinated_criteria_downgrade_cannot_replace_host_authority():
    authoritative_criteria = _criteria()
    authoritative_result = _result()
    authority = _authority_snapshot(authoritative_criteria, (authoritative_result,))
    worker_criteria = replace(authoritative_criteria, evidence_requirements=())

    with pytest.raises(OutcomeContractError, match="host-attested criteria hash"):
        _decision(
            criteria=worker_criteria,
            results=(authoritative_result,),
            authority_snapshot=authority,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"task_input_hash": "d" * 64}, "host task definition"),
        ({"result_schema_hash": "e" * 64}, "host task definition"),
        ({"assignment_id": "assignment-substituted"}, "coordinator attestation"),
        (
            {
                "validation_authority": ResultValidationAuthority(
                    principal_id="coordinator:substituted",
                    authority_source="worker-claim",
                    authority_version="1",
                )
            },
            "coordinator attestation",
        ),
    ],
)
def test_accepted_result_must_match_host_task_and_coordinator_binding(
    mutation, message
):
    criteria = _criteria()
    authoritative_result = _result()
    submitted_result = _result(**mutation)
    authority = _authority_snapshot(criteria, (authoritative_result,))

    with pytest.raises(OutcomeContractError, match=message):
        _decision(
            criteria=criteria,
            results=(submitted_result,),
            authority_snapshot=authority,
        )


def test_attempt_substitution_cannot_replace_host_task_binding():
    criteria = _criteria()
    authoritative_result = _result()
    substituted_evidence = _evidence(attempt_id="attempt-substituted")
    submitted_result = _result(
        attempt_id="attempt-substituted",
        evidence_digest=evidence_set_digest((substituted_evidence,)),
    )
    authority = _authority_snapshot(criteria, (authoritative_result,))

    with pytest.raises(OutcomeContractError, match="coordinator attestation"):
        _decision(
            criteria=criteria,
            results=(submitted_result,),
            evidence=(substituted_evidence,),
            authority_snapshot=authority,
        )


def test_duplicate_provider_receipt_cannot_satisfy_minimum_evidence_count():
    evidence = (
        _evidence(),
        _evidence(evidence_id="evidence-2"),
    )
    criteria = _criteria(evidence_requirements=(_requirement(min_items=2),))
    result = _result(
        evidence_ids=("evidence-1", "evidence-2"),
        evidence_digest=evidence_set_digest(evidence),
        coverage=(
            CoverageClaim(
                requirement_id="requirement-a",
                status=CoverageStatus.SATISFIED,
                evidence_ids=("evidence-1", "evidence-2"),
            ),
        ),
    )

    with pytest.raises(
        OutcomeContractError, match="source-scoped receipt can identify only one"
    ):
        _decision(criteria=criteria, results=(result,), evidence=evidence)


def test_same_local_receipt_value_from_distinct_sources_is_not_a_duplicate():
    second_provenance = EvidenceProvenance(
        source_type="provider_api",
        source_id="validation-job:provider-b-job-1",
        source_version="2",
        source_contract_hash="d" * 64,
        producer_principal_id="internal-agent:validator-b",
        capability_id="request_synthetic_validation",
        tool_id="validation.request_synthetic",
    )
    evidence = (
        _evidence(),
        _evidence(
            evidence_id="evidence-2",
            content_hash="e" * 64,
            provenance=second_provenance,
            observed_at=NOW + timedelta(seconds=1),
            recorded_at=NOW + timedelta(seconds=2),
        ),
    )
    criteria = _criteria(evidence_requirements=(_requirement(min_items=2),))
    result = _result(
        evidence_ids=("evidence-1", "evidence-2"),
        evidence_digest=evidence_set_digest(evidence),
        coverage=(
            CoverageClaim(
                requirement_id="requirement-a",
                status=CoverageStatus.SATISFIED,
                evidence_ids=("evidence-1", "evidence-2"),
            ),
        ),
    )

    decision = _decision(criteria=criteria, results=(result,), evidence=evidence)

    assert decision.status is CompletionStatus.COMPLETE


def test_all_result_evidence_must_belong_to_the_exact_task_attempt():
    evidence = (
        _evidence(),
        _evidence(
            evidence_id="evidence-2",
            task_id="task-b",
            attempt_id="attempt-b1",
            receipt_id="validation-job:job-2",
            provenance=EvidenceProvenance(
                source_type="provider_api",
                source_id="validation-job:job-2",
                source_version="1",
                source_contract_hash=HASH_B,
                producer_principal_id="internal-agent:validator",
                capability_id="request_synthetic_validation",
                tool_id="validation.request_synthetic",
            ),
        ),
    )
    result = _result(
        evidence_ids=("evidence-1", "evidence-2"),
        evidence_digest=evidence_set_digest(evidence),
    )

    with pytest.raises(OutcomeContractError, match="every result evidence member"):
        _decision(results=(result,), evidence=evidence)


def test_old_decision_is_stale_against_independent_current_stream_cursor():
    decision = _decision(authoritative_event_sequence=14)
    projection = project_completion(
        decision,
        decision_hash=completion_decision_digest(decision),
        authoritative_stream_sequence=15,
        projected_event_sequence=15,
        projected_at=NOW + timedelta(minutes=11),
    )

    assert projection.display_status is CompletionDisplayStatus.STALE
    assert projection.projection_lag == 0
    assert projection.decision_lag == 1
