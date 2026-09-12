from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import timedelta

import pytest

from api.composition import default_deps
from application.services.workflow_outcomes import (
    OutcomeLedgerConflict,
    WorkflowOutcomeService,
)
from domain.workflow.outcome_authority_serialization import (
    completion_authority_snapshot_digest,
)
from domain.workflow.outcome_serialization import (
    completion_criteria_digest,
    completion_decision_digest,
    evidence_digest,
    evidence_payload,
    task_result_digest,
)
from domain.workflow.outcomes import (
    AuthoritativeTaskDefinition,
    CompletionStatus,
    ContractAuthority,
    CoverageClaim,
    CoverageStatus,
    EvidenceProvenance,
    EvidenceRequirement,
    OutcomeContractError,
    ResultValidationAuthority,
)
from infrastructure.db.core.connection import get_connection
from infrastructure.db.workflow.outcome_rows import (
    OutcomeLedgerDataError,
    canonical_json,
)
from tests.modules.workflow_outcome_ledger_support import (
    HOST_AUTHORITY,
    NOW,
    command,
    coordinator_command,
    create_workflow,
    criteria,
    evidence,
    evidence_command,
    publisher_command,
    result,
    service,
    task_definitions,
    with_outcome_ledger,
)


@pytest.fixture
def outcome_deps(tmp_path):
    app_deps = default_deps()
    app_deps.set_database_path(tmp_path / "workflow-outcomes.db")
    app_deps.init_db()
    return with_outcome_ledger(app_deps)


def _publish_complete_inputs(deps, workflow_id: str):
    outcome_service = service(deps)
    evidence_value = evidence(workflow_id)
    result_value = result(workflow_id, (evidence_value,))
    outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    outcome_service.record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )
    outcome_service.record_task_result(
        command=coordinator_command(workflow_id, "command-result"),
        result=result_value,
    )
    return outcome_service, evidence_value, result_value


def _json_digest(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _request_hash(command_type: str, request: dict[str, object]) -> str:
    return _json_digest({"command_type": command_type, "request": request})


def _definitions_hash(definitions) -> str:
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


def _persist_complete_decision(deps, workflow_id: str):
    outcome_service, evidence_value, result_value = _publish_complete_inputs(
        deps, workflow_id
    )
    publication = deps.workflow_outcomes.get_completion_contract(
        tenant_id="tenant-a", workflow_id=workflow_id, criteria_id="criteria-a"
    )
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-a",
        criteria_id="criteria-a",
        criteria_hash=publication["criteria_digest"],
    )
    outcome_service.evaluate_and_record(
        command=command(
            workflow_id,
            command_id="command-decision",
            issued_at=NOW + timedelta(minutes=50),
        ),
        snapshot_id="snapshot-a",
        decision_id="decision-a",
        evaluated_at=NOW + timedelta(minutes=40),
        authoritative_event_sequence=14,
    )
    return outcome_service, evidence_value, result_value, publication


def test_durable_decision_reproduces_after_connection_restart(outcome_deps, tmp_path):
    workflow_id = create_workflow(outcome_deps)
    outcome_service, evidence_value, result_value = _publish_complete_inputs(
        outcome_deps, workflow_id
    )
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-a",
        criteria_id="criteria-a",
        criteria_hash=outcome_deps.workflow_outcomes.get_completion_contract(
            tenant_id="tenant-a",
            workflow_id=workflow_id,
            criteria_id="criteria-a",
        )["criteria_digest"],
    )
    write = outcome_service.evaluate_and_record(
        command=command(
            workflow_id,
            command_id="command-decision",
            issued_at=NOW + timedelta(minutes=50),
        ),
        snapshot_id="snapshot-a",
        decision_id="decision-a",
        evaluated_at=NOW + timedelta(minutes=40),
        authoritative_event_sequence=14,
    )
    assert write["outcome"] == "applied"

    database_path = tmp_path / "workflow-outcomes.db"
    restarted_app_deps = default_deps()
    restarted_app_deps.set_database_path(database_path)
    restarted_app_deps.init_db()
    restarted_deps = with_outcome_ledger(restarted_app_deps)
    reproduced = WorkflowOutcomeService(
        store=restarted_deps.workflow_outcomes,
        host_authority=HOST_AUTHORITY,
    ).reproduce_decision(
        tenant_id="tenant-a",
        workflow_id=workflow_id,
        decision_id="decision-a",
    )

    assert reproduced.status is CompletionStatus.COMPLETE
    assert reproduced.accepted_result_ids == (result_value.result_id,)
    assert reproduced.evidence_ids == (evidence_value.evidence_id,)
    assert completion_decision_digest(reproduced) == write["artifact_digest"]
    assert (
        restarted_deps.agent_runs.get_agent_run(
            run_id=workflow_id, client_id="tenant-a"
        )["status"]
        == "planned"
    )


def test_missing_result_is_persisted_as_honest_incomplete_decision(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-empty",
        criteria_id="criteria-a",
        criteria_hash=publication["artifact_digest"],
    )
    outcome_service.evaluate_and_record(
        command=command(
            workflow_id,
            command_id="command-decision",
            issued_at=NOW + timedelta(minutes=50),
        ),
        snapshot_id="snapshot-empty",
        decision_id="decision-incomplete",
        evaluated_at=NOW + timedelta(minutes=40),
        authoritative_event_sequence=14,
    )

    decision = outcome_deps.workflow_outcomes.get_completion_decision(
        tenant_id="tenant-a",
        workflow_id=workflow_id,
        decision_id="decision-incomplete",
    )["decision"]
    assert decision.status is CompletionStatus.INCOMPLETE
    assert decision.missing_result_task_ids == ("task-a",)


def test_idempotency_replays_exact_write_and_rejects_changed_payload(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    first_command = evidence_command(workflow_id, "command-evidence")
    first = outcome_service.record_evidence(
        command=first_command, evidence=evidence(workflow_id)
    )
    replay = outcome_service.record_evidence(
        command=replace(first_command, command_id="command-evidence-retry"),
        evidence=evidence(workflow_id),
    )
    assert first["outcome"] == "applied"
    assert replay == {**first, "outcome": "replayed"}

    with pytest.raises(OutcomeLedgerConflict, match="idempotency key"):
        outcome_service.record_evidence(
            command=replace(first_command, command_id="command-evidence-conflict"),
            evidence=evidence(workflow_id, content_hash="d" * 64),
        )


def test_result_cannot_bind_cross_attempt_or_cross_tenant_evidence(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    evidence_value = evidence(workflow_id)
    outcome_service.record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )
    with pytest.raises(OutcomeLedgerConflict, match="exact attempt"):
        outcome_service.record_task_result(
            command=coordinator_command(workflow_id, "command-result-wrong-attempt"),
            result=result(
                workflow_id,
                (evidence_value,),
                result_id="result-wrong-attempt",
                attempt_id="attempt-other",
            ),
        )

    other_workflow_id = create_workflow(outcome_deps, tenant_id="tenant-b")
    cross_tenant_result = result(
        other_workflow_id,
        (evidence_value,),
        result_id="result-cross-tenant",
        tenant_id="tenant-b",
    )
    with pytest.raises(OutcomeLedgerConflict, match="evidence does not exist"):
        outcome_service.record_task_result(
            command=command(
                other_workflow_id,
                command_id="command-result-cross-tenant",
                tenant_id="tenant-b",
                principal_id="coordinator:workflow",
                authority_source="workflow-coordinator",
                authority_version="v1",
            ),
            result=cross_tenant_result,
        )


@pytest.mark.parametrize(
    ("evidence_times", "result_times", "message"),
    [
        (
            {
                "observed_at": NOW + timedelta(minutes=10),
                "recorded_at": NOW + timedelta(minutes=11),
            },
            {
                "created_at": NOW + timedelta(minutes=3),
                "validated_at": NOW + timedelta(minutes=12),
            },
            "observed after result creation",
        ),
        (
            {"recorded_at": NOW + timedelta(minutes=10)},
            {
                "created_at": NOW + timedelta(minutes=3),
                "validated_at": NOW + timedelta(minutes=4),
            },
            "recorded after result validation",
        ),
    ],
)
def test_persistence_rejects_result_evidence_outside_its_causal_window(
    outcome_deps, evidence_times, result_times, message
):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    evidence_value = evidence(workflow_id, **evidence_times)
    outcome_service.record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )

    with pytest.raises(OutcomeLedgerConflict, match=message):
        outcome_service.record_task_result(
            command=coordinator_command(workflow_id, "command-result"),
            result=result(workflow_id, (evidence_value,), **result_times),
        )


def test_validated_result_requires_configured_coordinator_authority(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    evidence_value = evidence(workflow_id)
    outcome_service = service(outcome_deps)
    outcome_service.record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )
    substituted = ResultValidationAuthority(
        principal_id="coordinator:forged",
        authority_source="worker-claim",
        authority_version="v1",
    )
    with pytest.raises(OutcomeContractError, match="configured coordinator"):
        outcome_service.record_task_result(
            command=coordinator_command(workflow_id, "command-result"),
            result=result(
                workflow_id,
                (evidence_value,),
                validation_authority=substituted,
            ),
        )


def test_publication_rejects_self_selected_host_authority(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    forged = ContractAuthority(
        principal_id="worker:self",
        authority_source="worker-result",
        authority_version="v1",
    )
    with pytest.raises(OutcomeContractError, match="configured host authority"):
        service(outcome_deps).publish_completion_contract(
            command=publisher_command(workflow_id, "command-publish"),
            criteria=criteria(workflow_id, publishing_authority=forged),
            task_definitions=task_definitions(),
        )


def test_snapshot_derives_results_from_host_state_and_rejects_ambiguity(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service, evidence_value, _ = _publish_complete_inputs(
        outcome_deps, workflow_id
    )
    outcome_service.record_task_result(
        command=coordinator_command(workflow_id, "command-result-second"),
        result=result(
            workflow_id,
            (evidence_value,),
            result_id="result-second",
        ),
    )
    publication = outcome_deps.workflow_outcomes.get_completion_contract(
        tenant_id="tenant-a",
        workflow_id=workflow_id,
        criteria_id="criteria-a",
    )

    with pytest.raises(OutcomeLedgerConflict, match="multiple results"):
        outcome_service.issue_authority_snapshot(
            command=command(workflow_id, command_id="command-snapshot"),
            snapshot_id="snapshot-ambiguous",
            criteria_id="criteria-a",
            criteria_hash=publication["criteria_digest"],
        )


def test_default_application_deps_do_not_expose_privileged_outcome_writer():
    assert not hasattr(default_deps(), "workflow_outcomes")


def test_adapter_rejects_worker_issued_accepted_result(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    evidence_value = evidence(workflow_id)
    service(outcome_deps).record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )
    result_value = result(workflow_id, (evidence_value,))
    digest = task_result_digest(result_value)

    write = outcome_deps.workflow_outcomes.append_task_result(
        command=command(
            workflow_id,
            command_id="command-worker-result",
            principal_id="worker:self",
            authority_source="worker-claim",
            authority_version="v1",
        ).persistence_payload("record_task_result"),
        result=result_value,
        request_hash=_request_hash("record_task_result", {"result_digest": digest}),
    )

    assert write["outcome"] == "conflict"
    assert "authority" in write["reason"]


def test_adapter_rejects_worker_issued_completion_contract(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    criteria_value = criteria(workflow_id)
    definitions = task_definitions()
    digest = completion_criteria_digest(criteria_value)
    request = {
        "criteria_hash": digest,
        "task_definitions_hash": _definitions_hash(definitions),
    }

    write = outcome_deps.workflow_outcomes.publish_completion_contract(
        command=command(
            workflow_id,
            command_id="command-worker-criteria",
            principal_id="worker:self",
            authority_source="worker-claim",
            authority_version="v1",
        ).persistence_payload("publish_completion_contract"),
        criteria=criteria_value,
        task_definitions=definitions,
        request_hash=_request_hash("publish_completion_contract", request),
    )

    assert write["outcome"] == "conflict"
    assert "authority" in write["reason"]


def test_adapter_rejects_worker_issued_authority_snapshot(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service, _, _ = _publish_complete_inputs(outcome_deps, workflow_id)
    publication = outcome_deps.workflow_outcomes.get_completion_contract(
        tenant_id="tenant-a", workflow_id=workflow_id, criteria_id="criteria-a"
    )
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-a",
        criteria_id="criteria-a",
        criteria_hash=publication["criteria_digest"],
    )
    snapshot = outcome_deps.workflow_outcomes.get_authority_snapshot(
        tenant_id="tenant-a", workflow_id=workflow_id, snapshot_id="snapshot-a"
    )["snapshot"]
    digest = completion_authority_snapshot_digest(snapshot)
    request = {"snapshot_id": "snapshot-worker", "snapshot_digest": digest}

    write = outcome_deps.workflow_outcomes.commit_authority_snapshot(
        command=command(
            workflow_id,
            command_id="command-worker-snapshot",
            principal_id="worker:self",
            authority_source="worker-claim",
            authority_version="v1",
        ).persistence_payload("issue_authority_snapshot"),
        snapshot_id="snapshot-worker",
        snapshot=snapshot,
        issued_at="2026-09-12T09:30:00.000000Z",
        request_hash=_request_hash("issue_authority_snapshot", request),
    )

    assert write["outcome"] == "conflict"
    assert "authority" in write["reason"]


def test_adapter_rejects_worker_issued_completion_decision(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    _, evidence_value, result_value, _ = _persist_complete_decision(
        outcome_deps, workflow_id
    )
    persisted = outcome_deps.workflow_outcomes.get_completion_decision(
        tenant_id="tenant-a", workflow_id=workflow_id, decision_id="decision-a"
    )["decision"]
    snapshot = outcome_deps.workflow_outcomes.get_authority_snapshot(
        tenant_id="tenant-a", workflow_id=workflow_id, snapshot_id="snapshot-a"
    )
    worker_decision = replace(persisted, decision_id="decision-worker")
    decision_digest = completion_decision_digest(worker_decision)
    request = {
        "snapshot_id": "snapshot-a",
        "snapshot_digest": snapshot["snapshot_digest"],
        "decision_digest": decision_digest,
    }

    write = outcome_deps.workflow_outcomes.commit_completion_decision(
        command=command(
            workflow_id,
            command_id="command-worker-decision",
            principal_id="worker:self",
            authority_source="worker-claim",
            authority_version="v1",
            issued_at=NOW + timedelta(minutes=50),
        ).persistence_payload("record_completion_decision"),
        decision=worker_decision,
        snapshot_id="snapshot-a",
        result_bindings=((result_value.result_id, task_result_digest(result_value)),),
        evidence_bindings=(
            (evidence_value.evidence_id, evidence_digest(evidence_value)),
        ),
        request_hash=_request_hash("record_completion_decision", request),
    )

    assert write["outcome"] == "conflict"
    assert "authority" in write["reason"]


@pytest.mark.parametrize(
    ("operation", "issued_at", "message"),
    [
        ("evidence", NOW + timedelta(seconds=1), "durable artifact time"),
        ("result", NOW + timedelta(seconds=3), "durable artifact time"),
        ("criteria", NOW - timedelta(seconds=1), "durable artifact time"),
    ],
)
def test_commands_cannot_claim_artifacts_from_the_future(
    outcome_deps, operation, issued_at, message
):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    evidence_value = evidence(workflow_id)
    with pytest.raises(OutcomeContractError, match=message):
        if operation == "evidence":
            outcome_service.record_evidence(
                command=evidence_command(
                    workflow_id, "command-time", issued_at=issued_at
                ),
                evidence=evidence_value,
            )
        elif operation == "result":
            outcome_service.record_task_result(
                command=coordinator_command(
                    workflow_id, "command-time", issued_at=issued_at
                ),
                result=result(workflow_id, (evidence_value,)),
            )
        else:
            outcome_service.publish_completion_contract(
                command=publisher_command(
                    workflow_id, "command-time", issued_at=issued_at
                ),
                criteria=criteria(workflow_id),
                task_definitions=task_definitions(),
            )


def test_adapter_rejects_command_and_artifact_scope_substitution(outcome_deps):
    workflow_a = create_workflow(outcome_deps)
    workflow_b = create_workflow(outcome_deps, tenant_id="tenant-b")
    evidence_b = evidence(
        workflow_b,
        tenant_id="tenant-b",
        evidence_id="evidence-b",
    )
    command_payload = evidence_command(
        workflow_a, "command-cross-scope"
    ).persistence_payload("record_evidence")
    request_payload = {"evidence_digest": evidence_digest(evidence_b)}

    write = outcome_deps.workflow_outcomes.append_evidence(
        command=command_payload,
        evidence=evidence_b,
        request_hash=_request_hash("record_evidence", request_payload),
    )

    assert write == {
        "outcome": "conflict",
        "reason": "command scope does not match artifact scope",
    }


def test_database_rejects_command_and_artifact_scope_substitution(outcome_deps):
    workflow_a = create_workflow(outcome_deps)
    workflow_b = create_workflow(outcome_deps, tenant_id="tenant-b")
    evidence_b = evidence(
        workflow_b,
        tenant_id="tenant-b",
        evidence_id="evidence-b",
    )
    digest = evidence_digest(evidence_b)
    command_value = evidence_command(
        workflow_a, "command-cross-scope-db"
    ).persistence_payload("record_evidence")
    conn = get_connection()
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
            command_value["command_id"],
            command_value["tenant_id"],
            command_value["workflow_id"],
            command_value["command_type"],
            command_value["principal_id"],
            command_value["authority_source"],
            command_value["authority_version"],
            command_value["idempotency_key"],
            "d" * 64,
            "evidence",
            evidence_b.evidence_id,
            digest,
            command_value["issued_at"],
            command_value["issued_at"],
        ),
    )
    payload = evidence_payload(evidence_b)

    with pytest.raises(sqlite3.IntegrityError, match="command binding"):
        conn.execute(
            """
            INSERT INTO workflow_evidence_records (
                evidence_id, evidence_digest, tenant_id, workflow_id,
                graph_revision, task_id, attempt_id, action_id, payload_json,
                recorded_at, command_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                evidence_b.evidence_id,
                digest,
                evidence_b.tenant_id,
                evidence_b.workflow_id,
                evidence_b.graph_revision,
                evidence_b.task_id,
                evidence_b.attempt_id,
                evidence_b.action_id,
                canonical_json(payload),
                payload["observation"]["recorded_at"],
                command_value["command_id"],
            ),
        )
    conn.rollback()


def test_multi_task_decision_uses_canonical_durable_bindings(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    evidence_a = evidence(workflow_id)
    evidence_b = evidence(
        workflow_id,
        evidence_id="evidence-b",
        task_id="task-b",
        attempt_id="attempt-b1",
        receipt_id="provider-receipt-b",
        provenance=EvidenceProvenance(
            source_type="provider",
            source_id="provider-job-b",
            source_version="v1",
            source_contract_hash="b" * 64,
            producer_principal_id="internal-agent:observer",
            capability_id="validation.observe",
            tool_id="validation.read_result",
        ),
    )
    result_a = result(workflow_id, (evidence_a,))
    result_b = result(
        workflow_id,
        (evidence_b,),
        result_id="result-b",
        task_id="task-b",
        attempt_id="attempt-b1",
        coverage=(
            CoverageClaim(
                requirement_id="requirement-b",
                status=CoverageStatus.SATISFIED,
                evidence_ids=("evidence-b",),
            ),
        ),
    )
    criteria_value = criteria(
        workflow_id,
        required_task_ids=("task-a", "task-b"),
        evidence_requirements=(
            criteria(workflow_id).evidence_requirements[0],
            EvidenceRequirement(
                requirement_id="requirement-b",
                task_id="task-b",
                min_items=1,
                max_age_seconds=3600,
                require_verified_receipt=True,
                allowed_source_types=("provider",),
            ),
        ),
    )
    definitions = (
        task_definitions()[0],
        AuthoritativeTaskDefinition(
            task_id="task-b",
            task_input_hash="b" * 64,
            result_schema_id="validation-result",
            result_schema_version="v1",
            result_schema_hash="c" * 64,
        ),
    )
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria_value,
        task_definitions=definitions,
    )
    for suffix, evidence_value in (("b", evidence_b), ("a", evidence_a)):
        outcome_service.record_evidence(
            command=evidence_command(workflow_id, f"command-evidence-{suffix}"),
            evidence=evidence_value,
        )
    for suffix, result_value in (("b", result_b), ("a", result_a)):
        outcome_service.record_task_result(
            command=coordinator_command(workflow_id, f"command-result-{suffix}"),
            result=result_value,
        )
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-multi",
        criteria_id="criteria-a",
        criteria_hash=publication["artifact_digest"],
    )
    outcome_service.evaluate_and_record(
        command=command(
            workflow_id,
            command_id="command-decision",
            issued_at=NOW + timedelta(minutes=50),
        ),
        snapshot_id="snapshot-multi",
        decision_id="decision-multi",
        evaluated_at=NOW + timedelta(minutes=40),
        authoritative_event_sequence=20,
    )

    persisted = outcome_deps.workflow_outcomes.get_completion_decision(
        tenant_id="tenant-a",
        workflow_id=workflow_id,
        decision_id="decision-multi",
    )["decision"]
    assert persisted.status is CompletionStatus.COMPLETE
    assert persisted.accepted_result_ids == ("result-a", "result-b")


def test_reads_detect_denormalized_column_corruption(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    service(outcome_deps).record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence(workflow_id),
    )
    conn = get_connection()
    conn.execute("DROP TRIGGER workflow_evidence_records_no_update")
    conn.execute("UPDATE workflow_evidence_records SET task_id = 'task-substituted'")
    conn.commit()

    with pytest.raises(OutcomeLedgerDataError, match="evidence task"):
        outcome_deps.workflow_outcomes.get_evidence(
            tenant_id="tenant-a",
            workflow_id=workflow_id,
            evidence_id="evidence-a",
        )


@pytest.mark.parametrize(
    ("relation", "trigger", "message"),
    [
        (
            "workflow_result_evidence",
            "workflow_result_evidence_no_delete",
            "result evidence bindings",
        ),
        (
            "workflow_completion_snapshot_results",
            "workflow_completion_snapshot_results_no_delete",
            "snapshot result bindings",
        ),
        (
            "workflow_completion_decision_results",
            "workflow_completion_decision_results_no_delete",
            "decision result bindings",
        ),
        (
            "workflow_completion_decision_evidence",
            "workflow_completion_decision_evidence_no_delete",
            "decision evidence bindings",
        ),
    ],
)
def test_restart_reads_reject_deleted_relationships(
    outcome_deps, relation, trigger, message
):
    workflow_id = create_workflow(outcome_deps)
    outcome_service, _, result_value, _ = _persist_complete_decision(
        outcome_deps, workflow_id
    )
    conn = get_connection()
    conn.execute(f"DROP TRIGGER {trigger}")
    conn.execute(f"DELETE FROM {relation}")
    conn.commit()

    with pytest.raises(OutcomeLedgerDataError, match=message):
        if relation == "workflow_result_evidence":
            outcome_deps.workflow_outcomes.get_task_result(
                tenant_id="tenant-a",
                workflow_id=workflow_id,
                result_id=result_value.result_id,
            )
        elif relation == "workflow_completion_snapshot_results":
            outcome_deps.workflow_outcomes.get_authority_snapshot(
                tenant_id="tenant-a",
                workflow_id=workflow_id,
                snapshot_id="snapshot-a",
            )
        else:
            outcome_service.reproduce_decision(
                tenant_id="tenant-a",
                workflow_id=workflow_id,
                decision_id="decision-a",
            )


@pytest.mark.parametrize(
    ("relation", "trigger", "id_column", "message"),
    [
        (
            "workflow_result_evidence",
            "workflow_result_evidence_no_update",
            "evidence_id",
            "result evidence bindings",
        ),
        (
            "workflow_completion_snapshot_results",
            "workflow_completion_snapshot_results_no_update",
            "result_id",
            "snapshot result binding does not resolve exactly",
        ),
        (
            "workflow_completion_decision_results",
            "workflow_completion_decision_results_no_update",
            "result_id",
            "decision result binding does not resolve exactly",
        ),
        (
            "workflow_completion_decision_evidence",
            "workflow_completion_decision_evidence_no_update",
            "evidence_id",
            "decision evidence binding does not resolve exactly",
        ),
    ],
)
def test_restart_reads_reject_relationship_id_digest_disagreement(
    outcome_deps, relation, trigger, id_column, message
):
    workflow_id = create_workflow(outcome_deps)
    outcome_service, _, result_value, _ = _persist_complete_decision(
        outcome_deps, workflow_id
    )
    conn = get_connection()
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute(f"DROP TRIGGER {trigger}")
    conn.execute(f"UPDATE {relation} SET {id_column} = 'tampered-id'")
    conn.commit()

    with pytest.raises(OutcomeLedgerDataError, match=message):
        if relation == "workflow_result_evidence":
            outcome_deps.workflow_outcomes.get_task_result(
                tenant_id="tenant-a",
                workflow_id=workflow_id,
                result_id=result_value.result_id,
            )
        elif relation == "workflow_completion_snapshot_results":
            outcome_deps.workflow_outcomes.get_authority_snapshot(
                tenant_id="tenant-a",
                workflow_id=workflow_id,
                snapshot_id="snapshot-a",
            )
        else:
            outcome_service.reproduce_decision(
                tenant_id="tenant-a",
                workflow_id=workflow_id,
                decision_id="decision-a",
            )


@pytest.mark.parametrize(
    "table",
    [
        "workflow_outcome_commands",
        "workflow_evidence_records",
        "workflow_task_results",
        "workflow_result_evidence",
        "workflow_completion_criteria",
        "workflow_completion_task_definitions",
        "workflow_completion_authority_snapshots",
        "workflow_completion_snapshot_results",
        "workflow_completion_decisions",
        "workflow_completion_decision_results",
        "workflow_completion_decision_evidence",
    ],
)
def test_outcome_ledger_tables_reject_update_and_delete(outcome_deps, table):
    workflow_id = create_workflow(outcome_deps)
    outcome_service, _, _ = _publish_complete_inputs(outcome_deps, workflow_id)
    publication = outcome_deps.workflow_outcomes.get_completion_contract(
        tenant_id="tenant-a", workflow_id=workflow_id, criteria_id="criteria-a"
    )
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-a",
        criteria_id="criteria-a",
        criteria_hash=publication["criteria_digest"],
    )
    outcome_service.evaluate_and_record(
        command=command(
            workflow_id,
            command_id="command-decision",
            issued_at=NOW + timedelta(minutes=50),
        ),
        snapshot_id="snapshot-a",
        decision_id="decision-a",
        evaluated_at=NOW + timedelta(minutes=40),
        authoritative_event_sequence=14,
    )
    conn = get_connection()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute(f"UPDATE {table} SET rowid = rowid")
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute(f"DELETE FROM {table}")
    conn.rollback()
