from __future__ import annotations

import sqlite3
from datetime import timedelta

import pytest

from api.composition import default_deps
from api.runtime_composition import default_completion_coordinator, default_runtime
from application.services.agent_runtime.runtime.payloads import hash_payload
from application.services.agent_runtime.runtime.status import derive_next_run_status
from application.services.workflow_outcomes import OutcomeLedgerConflict
from domain.workflow.outcomes import OutcomeContractError, ResultValidationStatus
from infrastructure.db.core.connection import get_connection
from tests.modules.workflow_outcome_ledger_support import (
    HASH_B,
    NOW,
    command,
    coordinator_command,
    create_workflow,
    criteria,
    evidence as support_evidence,
    evidence_command,
    publisher_command,
    result as support_result,
    service,
    task_definitions as support_task_definitions,
    with_outcome_ledger,
)


EMPTY_PAYLOAD_HASH = hash_payload({})


def task_definitions():
    definition = support_task_definitions()[0]
    return (
        definition.__class__(
            task_id=definition.task_id,
            task_input_hash=EMPTY_PAYLOAD_HASH,
            result_schema_id=definition.result_schema_id,
            result_schema_version=definition.result_schema_version,
            result_schema_hash=definition.result_schema_hash,
        ),
    )


def evidence(workflow_id: str, **overrides):
    overrides.setdefault("content_hash", EMPTY_PAYLOAD_HASH)
    return support_evidence(workflow_id, **overrides)


def result(workflow_id: str, evidence_values, **overrides):
    overrides.setdefault("task_input_hash", EMPTY_PAYLOAD_HASH)
    overrides.setdefault("payload_hash", EMPTY_PAYLOAD_HASH)
    return support_result(
        workflow_id,
        evidence_values,
        **overrides,
    )


@pytest.fixture
def outcome_deps(tmp_path):
    app_deps = default_deps()
    app_deps.set_database_path(tmp_path / "workflow-completion-lifecycle.db")
    app_deps.init_db()
    return with_outcome_ledger(app_deps)


def _bind_test_attempt(deps, workflow_id: str) -> str:
    action = deps.agent_actions.create_agent_action(
        agent_run_id=workflow_id,
        sequence=1,
        status="executed",
        capability_name="test.result",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=HASH_B,
        outputs_hash=HASH_B,
        rationale="Host-owned test attempt",
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    get_connection().execute(
        """
        INSERT INTO workflow_completion_attempt_authorities (
            tenant_id, workflow_id, graph_revision, task_id, attempt_id,
            assignment_id, producer_principal_id, action_id, created_at
        ) VALUES ('tenant-a', ?, 1, 'task-a', 'attempt-a1', NULL,
                  'internal-agent:validator', ?, ?)
        """,
        (workflow_id, action["id"], NOW.isoformat()),
    )
    get_connection().commit()
    lock_token = "test-result-validation-lease"
    assert deps.agent_runs.acquire_run_lock(
        run_id=workflow_id, lock_token=lock_token, ttl_seconds=30
    )
    return lock_token


def _prepare_snapshot(deps, workflow_id: str, *, with_result: bool = True):
    outcome_service = service(deps)
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    if with_result:
        lock_token = _bind_test_attempt(deps, workflow_id)
        evidence_value = evidence(workflow_id)
        pending = result(
            workflow_id,
            (evidence_value,),
            validation_status=ResultValidationStatus.PENDING,
            validation_authority=None,
            validated_at=None,
        )
        outcome_service.record_evidence(
            command=evidence_command(workflow_id, "command-evidence"),
            evidence=evidence_value,
        )
        validation = outcome_service.validate_submitted_result(
            command=coordinator_command(workflow_id, "command-validation"),
            submitted_result=pending,
            criteria_id="criteria-a",
            criteria_hash=publication["artifact_digest"],
            validation_status=ResultValidationStatus.ACCEPTED,
            lock_token=lock_token,
        )
        assert validation["outcome"] == "applied"
        deps.agent_runs.release_run_lock(run_id=workflow_id, lock_token=lock_token)
    outcome_service.issue_authority_snapshot(
        command=command(workflow_id, command_id="command-snapshot"),
        snapshot_id="snapshot-a",
        criteria_id="criteria-a",
        criteria_hash=publication["artifact_digest"],
    )
    deps.agent_runs.update_agent_run(run_id=workflow_id, status="running")
    return outcome_service


def _decision_command(workflow_id: str):
    return command(
        workflow_id,
        command_id="command-decision",
        issued_at=NOW + timedelta(minutes=50),
    )


def _commit(outcome_service, workflow_id: str):
    return outcome_service.evaluate_and_commit_lifecycle(
        command=_decision_command(workflow_id),
        snapshot_id="snapshot-a",
        decision_id="decision-a",
        evaluated_at=NOW + timedelta(minutes=40),
    )


def test_coordinator_validates_worker_result_against_host_task_contract(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    lock_token = _bind_test_attempt(outcome_deps, workflow_id)
    evidence_value = evidence(workflow_id)
    outcome_service.record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )
    pending = result(
        workflow_id,
        (evidence_value,),
        validation_status=ResultValidationStatus.PENDING,
        validation_authority=None,
        validated_at=None,
    )

    write = outcome_service.validate_submitted_result(
        command=coordinator_command(workflow_id, "command-validation"),
        submitted_result=pending,
        criteria_id="criteria-a",
        criteria_hash=publication["artifact_digest"],
        validation_status=ResultValidationStatus.ACCEPTED,
        lock_token=lock_token,
    )

    persisted = outcome_deps.workflow_outcomes.get_task_result(
        tenant_id="tenant-a", workflow_id=workflow_id, result_id="result-a"
    )["result"]
    assert write["outcome"] == "applied"
    assert persisted.validation_status is ResultValidationStatus.ACCEPTED
    assert persisted.validated_at == NOW + timedelta(minutes=30)


def test_coordinator_rejects_substituted_task_contract(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    lock_token = _bind_test_attempt(outcome_deps, workflow_id)
    evidence_value = evidence(workflow_id)
    pending = result(
        workflow_id,
        (evidence_value,),
        task_input_hash="d" * 64,
        validation_status=ResultValidationStatus.PENDING,
        validation_authority=None,
        validated_at=None,
    )

    with pytest.raises(OutcomeContractError, match="authoritative task contract"):
        outcome_service.validate_submitted_result(
            command=coordinator_command(workflow_id, "command-validation"),
            submitted_result=pending,
            criteria_id="criteria-a",
            criteria_hash=publication["artifact_digest"],
            validation_status=ResultValidationStatus.ACCEPTED,
            lock_token=lock_token,
        )


def test_coordinator_rejects_worker_attempt_identity_substitution(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    lock_token = _bind_test_attempt(outcome_deps, workflow_id)
    evidence_value = evidence(workflow_id, attempt_id="substituted-attempt")
    pending = result(
        workflow_id,
        (evidence_value,),
        attempt_id="substituted-attempt",
        validation_status=ResultValidationStatus.PENDING,
        validation_authority=None,
        validated_at=None,
    )

    with pytest.raises(OutcomeContractError, match="host-selected task attempt"):
        outcome_service.validate_submitted_result(
            command=coordinator_command(workflow_id, "command-validation"),
            submitted_result=pending,
            criteria_id="criteria-a",
            criteria_hash=publication["artifact_digest"],
            validation_status=ResultValidationStatus.ACCEPTED,
            lock_token=lock_token,
        )


def test_result_validation_rechecks_lease_inside_the_write_transaction(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = service(outcome_deps)
    publication = outcome_service.publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    lock_token = _bind_test_attempt(outcome_deps, workflow_id)
    evidence_value = evidence(workflow_id)
    outcome_service.record_evidence(
        command=evidence_command(workflow_id, "command-evidence"),
        evidence=evidence_value,
    )
    pending = result(
        workflow_id,
        (evidence_value,),
        validation_status=ResultValidationStatus.PENDING,
        validation_authority=None,
        validated_at=None,
    )
    original = outcome_deps.workflow_outcomes.append_task_result

    def lose_lease(**kwargs):
        outcome_deps.agent_runs.release_run_lock(
            run_id=workflow_id, lock_token=lock_token
        )
        return original(**kwargs)

    outcome_deps.workflow_outcomes.append_task_result = lose_lease
    with pytest.raises(OutcomeLedgerConflict, match="attempt authority"):
        outcome_service.validate_submitted_result(
            command=coordinator_command(workflow_id, "command-validation"),
            submitted_result=pending,
            criteria_id="criteria-a",
            criteria_hash=publication["artifact_digest"],
            validation_status=ResultValidationStatus.ACCEPTED,
            lock_token=lock_token,
        )


def test_complete_decision_and_terminal_projection_commit_atomically(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)

    write = _commit(outcome_service, workflow_id)

    run = outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)
    projection = outcome_deps.workflow_outcomes.get_completion_projection(
        tenant_id="tenant-a", workflow_id=workflow_id
    )
    assert write["outcome"] == "applied"
    assert run["status"] == "completed"
    assert run["completion_authority_required"] is True
    assert projection["completion_status"] == "complete"
    assert projection["decision_id"] == "decision-a"
    conn = get_connection()
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM workflow_completion_lifecycle_events"
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE event_type = ?",
            ("completion_decision_recorded",),
        ).fetchone()[0]
        == 1
    )


def test_missing_result_persists_incomplete_without_completing_run(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id, with_result=False)

    _commit(outcome_service, workflow_id)

    run = outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)
    projection = run["completion_projection"]
    assert run["status"] == "running"
    assert projection["completion_status"] == "incomplete"
    assert projection["blockers"]["missing_result_task_ids"] == ["task-a"]


def test_direct_action_derived_completion_is_rejected_for_governed_run(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    service(outcome_deps).publish_completion_contract(
        command=publisher_command(workflow_id, "command-publish"),
        criteria=criteria(workflow_id),
        task_definitions=task_definitions(),
    )
    run = outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)

    status, _ = derive_next_run_status(run=run, actions=[{"status": "executed"}])
    assert status == "planned"
    with pytest.raises(sqlite3.IntegrityError, match="exact COMPLETE"):
        outcome_deps.agent_runs.update_agent_run(run_id=workflow_id, status="completed")


def test_concurrent_replan_invalidates_completion_fence(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    original = outcome_deps.workflow_outcomes.commit_completion_decision

    def interleaved_commit(**kwargs):
        outcome_deps.agent_actions.create_agent_action(
            agent_run_id=workflow_id,
            sequence=2,
            status="proposed",
            capability_name="review_validation_readiness",
            capability_version="v1",
            inputs={},
            outputs={},
            inputs_hash=None,
            outputs_hash=None,
            rationale="Concurrent replan",
            confidence=None,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
        )
        return original(**kwargs)

    outcome_deps.workflow_outcomes.commit_completion_decision = interleaved_commit
    with pytest.raises(OutcomeLedgerConflict, match="projection changed"):
        _commit(outcome_service, workflow_id)

    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)["status"] == "running"
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_decisions")
        .fetchone()[0]
        == 0
    )


def test_cancellation_wins_without_partial_completion_commit(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    original = outcome_deps.workflow_outcomes.commit_completion_decision

    def interleaved_commit(**kwargs):
        outcome_deps.agent_runs.transition_agent_run_status(
            run_id=workflow_id,
            expected_statuses=("running",),
            status="canceled",
        )
        return original(**kwargs)

    outcome_deps.workflow_outcomes.commit_completion_decision = interleaved_commit
    with pytest.raises(OutcomeLedgerConflict, match="projection changed"):
        _commit(outcome_service, workflow_id)

    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)["status"]
        == "canceled"
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_decisions")
        .fetchone()[0]
        == 0
    )


def test_completion_wins_and_late_cancellation_cannot_overwrite_it(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    _commit(outcome_service, workflow_id)

    canceled = outcome_deps.agent_runs.transition_agent_run_status(
        run_id=workflow_id,
        expected_statuses=("running",),
        status="canceled",
    )

    assert canceled is None
    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)["status"]
        == "completed"
    )


def test_completed_governed_run_cannot_hide_a_new_action(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    _commit(outcome_service, workflow_id)

    with pytest.raises(sqlite3.IntegrityError, match="cannot acquire new actions"):
        outcome_deps.agent_actions.create_agent_action(
            agent_run_id=workflow_id,
            sequence=2,
            status="proposed",
            capability_name="review_validation_readiness",
            capability_version="v1",
            inputs={},
            outputs={},
            inputs_hash=None,
            outputs_hash=None,
            rationale="Late replan",
            confidence=None,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
        )

    assert (
        len(
            outcome_deps.agent_actions.list_agent_actions(
                agent_run_id=workflow_id, limit=10
            )
        )
        == 1
    )

    existing = outcome_deps.agent_actions.list_agent_actions(
        agent_run_id=workflow_id, limit=10
    )[0]
    with pytest.raises(sqlite3.IntegrityError, match="action status is immutable"):
        outcome_deps.agent_actions.update_agent_action_status(
            action_id=existing["id"], status="proposed"
        )
    with pytest.raises(sqlite3.IntegrityError, match="action status is immutable"):
        outcome_deps.agent_actions.update_agent_action_status(
            action_id=existing["id"],
            status="executed",
            outputs={"tampered": True},
        )

    persisted = outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)
    assert persisted["completion_projection_is_current"] is True
    assert persisted["status"] == "completed"


def test_unknown_action_status_is_rejected_and_cannot_fail_open(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    with pytest.raises(ValueError, match="closed agent-action lifecycle"):
        outcome_deps.agent_actions.create_agent_action(
            agent_run_id=workflow_id,
            sequence=1,
            status="queued",
            capability_name="review_validation_readiness",
            capability_version="v1",
            inputs={},
            outputs={},
            inputs_hash=None,
            outputs_hash=None,
            rationale="Unknown state",
            confidence=None,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
        )
    action = outcome_deps.agent_actions.create_agent_action(
        agent_run_id=workflow_id,
        sequence=1,
        status="proposed",
        capability_name="review_validation_readiness",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Known state",
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    with pytest.raises(sqlite3.IntegrityError, match="outside the closed lifecycle"):
        get_connection().execute(
            "UPDATE agent_actions SET status = 'queued' WHERE id = ?",
            (action["id"],),
        )
    get_connection().rollback()


def test_active_worker_lease_blocks_completion(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    assert outcome_deps.agent_runs.acquire_run_lock(
        run_id=workflow_id, lock_token="worker-lease-a", ttl_seconds=30
    )

    with pytest.raises(OutcomeLedgerConflict, match="lease ownership"):
        _commit(outcome_service, workflow_id)

    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)["status"] == "running"
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_decisions")
        .fetchone()[0]
        == 0
    )


def test_newer_active_criteria_prevents_old_snapshot_completion(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    outcome_service.publish_completion_contract(
        command=publisher_command(
            workflow_id,
            "command-publish-v2",
            issued_at=NOW + timedelta(minutes=35),
        ),
        criteria=criteria(
            workflow_id,
            criteria_id="criteria-b",
            criteria_version="v2",
            created_at=NOW + timedelta(minutes=31),
        ),
        task_definitions=task_definitions(),
    )

    with pytest.raises(OutcomeLedgerConflict, match="active criteria"):
        _commit(outcome_service, workflow_id)

    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)["status"] == "running"
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_decisions")
        .fetchone()[0]
        == 0
    )


def test_new_criteria_marks_an_existing_incomplete_projection_stale(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id, with_result=False)
    _commit(outcome_service, workflow_id)
    outcome_service.publish_completion_contract(
        command=publisher_command(
            workflow_id,
            "command-publish-v2",
            issued_at=NOW + timedelta(minutes=55),
        ),
        criteria=criteria(
            workflow_id,
            criteria_id="criteria-b",
            criteria_version="v2",
            created_at=NOW + timedelta(minutes=51),
        ),
        task_definitions=task_definitions(),
    )

    run = outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)
    assert run["completion_projection"]["completion_status"] == "incomplete"
    assert run["completion_projection_is_current"] is False


def test_action_drift_marks_an_incomplete_projection_stale(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id, with_result=False)
    _commit(outcome_service, workflow_id)
    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)[
            "completion_projection_is_current"
        ]
        is True
    )

    outcome_deps.agent_actions.create_agent_action(
        agent_run_id=workflow_id,
        sequence=1,
        status="proposed",
        capability_name="review_validation_readiness",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Action projection changed",
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )

    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)[
            "completion_projection_is_current"
        ]
        is False
    )


def test_completion_projection_cannot_move_to_an_older_event_cursor(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id, with_result=False)
    _commit(outcome_service, workflow_id)

    with pytest.raises(OutcomeContractError, match="allocated by the host"):
        outcome_service.evaluate_and_commit_lifecycle(
            command=command(
                workflow_id,
                command_id="command-decision-older",
                issued_at=NOW + timedelta(minutes=55),
            ),
            snapshot_id="snapshot-a",
            decision_id="decision-older",
            evaluated_at=NOW + timedelta(minutes=45),
            authoritative_event_sequence=13,
        )

    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_decisions")
        .fetchone()[0]
        == 1
    )


def test_duplicate_completion_delivery_replays_without_duplicate_events(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)

    assert _commit(outcome_service, workflow_id)["outcome"] == "applied"
    assert _commit(outcome_service, workflow_id)["outcome"] == "replayed"

    conn = get_connection()
    assert (
        conn.execute("SELECT COUNT(*) FROM workflow_completion_decisions").fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM workflow_completion_lifecycle_events"
        ).fetchone()[0]
        == 1
    )


def test_historical_decision_reconstructs_after_projection_advances(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id, with_result=False)
    _commit(outcome_service, workflow_id)
    outcome_deps.agent_actions.create_agent_action(
        agent_run_id=workflow_id,
        sequence=2,
        status="proposed",
        capability_name="review_validation_readiness",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Advance the projection without replacing history",
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    outcome_service.evaluate_and_commit_lifecycle(
        command=command(
            workflow_id,
            command_id="command-decision-b",
            issued_at=NOW + timedelta(minutes=60),
        ),
        snapshot_id="snapshot-a",
        decision_id="decision-b",
        evaluated_at=NOW + timedelta(minutes=55),
    )

    historical = outcome_service.reproduce_decision(
        tenant_id="tenant-a", workflow_id=workflow_id, decision_id="decision-a"
    )

    assert historical.status.value == "incomplete"
    rows = get_connection().execute(
        """
        SELECT decision_id, projected_run_state
        FROM workflow_completion_lifecycle_events
        WHERE workflow_id = ? ORDER BY authoritative_event_sequence
        """,
        (workflow_id,),
    ).fetchall()
    assert [(row["decision_id"], row["projected_run_state"]) for row in rows] == [
        ("decision-a", "planned"),
        ("decision-b", "planned"),
    ]


def test_lifecycle_event_failure_rolls_back_decision_and_projection(outcome_deps):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    conn = get_connection()
    conn.execute(
        """
        CREATE TRIGGER fail_completion_lifecycle_event
        BEFORE INSERT ON workflow_completion_lifecycle_events
        BEGIN
            SELECT RAISE(ABORT, 'simulated lifecycle write failure');
        END
        """
    )
    conn.commit()

    with pytest.raises(OutcomeLedgerConflict, match="simulated lifecycle"):
        _commit(outcome_service, workflow_id)

    assert (
        outcome_deps.agent_runs.get_agent_run(run_id=workflow_id)["status"] == "running"
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM workflow_completion_decisions").fetchone()[0]
        == 0
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM workflow_completion_projections").fetchone()[
            0
        ]
        == 0
    )


def test_completed_projection_reconstructs_after_restart(outcome_deps, tmp_path):
    workflow_id = create_workflow(outcome_deps)
    outcome_service = _prepare_snapshot(outcome_deps, workflow_id)
    write = _commit(outcome_service, workflow_id)

    restarted_app_deps = default_deps()
    restarted_app_deps.set_database_path(tmp_path / "workflow-completion-lifecycle.db")
    restarted_app_deps.init_db()
    restarted = with_outcome_ledger(restarted_app_deps)
    run = restarted.agent_runs.get_agent_run(run_id=workflow_id, client_id="tenant-a")
    projection = restarted.workflow_outcomes.get_completion_projection(
        tenant_id="tenant-a", workflow_id=workflow_id
    )

    assert run["status"] == "completed"
    assert run["completion_projection"] == projection
    assert projection["decision_digest"] == write["artifact_digest"]
    assert (
        service(restarted)
        .reproduce_decision(
            tenant_id="tenant-a",
            workflow_id=workflow_id,
            decision_id="decision-a",
        )
        .status.value
        == "complete"
    )


def test_production_sequential_runtime_uses_host_completion_coordinator(
    tmp_path, monkeypatch
):
    deps = default_deps()
    deps.set_database_path(tmp_path / "production-completion-runtime.db")
    deps.init_db()
    deps.clients.create_client(client_id="tenant-runtime", name="Runtime tenant")
    run = deps.agent_runs.create_agent_run(
        client_id="tenant-runtime",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"objective_id": "objective-runtime"},
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=False,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:sequential-worker",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="approved",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        inputs={"experiment_id": "experiment-runtime"},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Production completion integration",
        confidence=0.9,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **_: {"status": "done", "protocol": "frozen"},
    )
    result_value = default_runtime(deps).step_once(
        run_id=run["id"], user_id="operator-runtime"
    )

    persisted = deps.agent_runs.get_agent_run(run_id=run["id"])
    conn = get_connection()
    assert result_value.action["id"] == action["id"]
    assert persisted["completion_authority_required"] is True
    assert persisted["completion_projection_is_current"] is True
    assert persisted["completion_projection"]["completion_status"] == "complete"
    assert persisted["completion_projection"]["projected_run_state"] == (
        "retrieval_snapshots_ready"
    )
    assert persisted["state"] == "retrieval_snapshots_ready"
    assert persisted["status"] == "completed"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM workflow_task_results WHERE workflow_id = ?",
            (run["id"],),
        ).fetchone()[0]
        == 1
    )


def test_all_rejected_governed_run_records_incomplete_and_becomes_non_runnable(
    tmp_path,
):
    deps = default_deps()
    deps.set_database_path(tmp_path / "all-rejected-completion.db")
    deps.init_db()
    deps.clients.create_client(client_id="tenant-rejected", name="Rejected tenant")
    run = deps.agent_runs.create_agent_run(
        client_id="tenant-rejected",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"objective_id": "objective-rejected"},
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=False,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:sequential-worker",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="proposed",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Rejected before execution",
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    coordinator = default_completion_coordinator(deps)
    coordinator.activate_run(run_id=run["id"])
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="rejected"
    )
    lock_token = "all-rejected-lock"
    assert deps.agent_runs.acquire_run_lock(
        run_id=run["id"], lock_token=lock_token, ttl_seconds=30
    )

    reconciled = coordinator.synchronize_run(
        run_id=run["id"], lock_token=lock_token
    )

    assert reconciled["status"] == "canceled"
    assert reconciled["completion_projection_is_current"] is True
    assert reconciled["completion_projection"]["completion_status"] == "incomplete"
