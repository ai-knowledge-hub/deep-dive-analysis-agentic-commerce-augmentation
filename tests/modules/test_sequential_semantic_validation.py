from __future__ import annotations

from dataclasses import replace
from datetime import timedelta

import pytest

from application.services.agent_runtime.runtime import AgentRuntimeService
from shared.db.connection import get_connection
from tests.modules.test_approval_effect_authorization import (
    _approve,
    _matching_validation_job,
    _run_and_action,
)
from tests.modules.test_sequential_workflow_compatibility import (
    TENANT_ID,
    _commit_initial_incomplete_decision,
    _seed_sequential_run,
)
from tests.modules.workflow_outcome_ledger_support import (
    NOW,
    command as outcome_command,
)


def test_queued_validation_receipt_remains_reconcilable_as_job_state_changes(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(
        tmp_path,
        action_inputs={"experiment_id": "experiment-a", "auto_run": False},
    )
    approved = _approve(deps, run, action)
    created_job = None

    def _effect(**kwargs):
        nonlocal created_job
        created_job = _matching_validation_job(
            deps,
            approved["action"],
            status="pending",
            with_result=False,
        )
        return {"validation_job_id": created_job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )
    assert result.action is not None
    assert result.action["status"] == "executed"
    assert created_job is not None
    get_connection().execute(
        """
        UPDATE agent_runs
        SET harness_id = 'harness.default', trace_id = 'trace-queued-semantic'
        WHERE id = ?
        """,
        (run["id"],),
    )
    get_connection().commit()

    first = deps.workflow_compatibility.project_sequential_run(
        tenant_id="client-a", run_id=run["id"]
    )
    before = deps.workflow_compatibility.get_sequential_projection(
        tenant_id="client-a", run_id=run["id"]
    )
    job_artifact = next(
        item
        for item in before["semantic_artifacts"]
        if item["artifact_type"] == "validation_job_receipt"
    )

    deps.validation_jobs.update_job_status(
        job_id=created_job["id"],
        client_id="client-a",
        status="running",
        model="provider-observed-model",
    )
    replay = deps.workflow_compatibility.project_sequential_run(
        tenant_id="client-a", run_id=run["id"]
    )
    after = deps.workflow_compatibility.get_sequential_projection(
        tenant_id="client-a", run_id=run["id"]
    )
    replayed_job_artifact = next(
        item
        for item in after["semantic_artifacts"]
        if item["artifact_type"] == "validation_job_receipt"
    )

    assert first["imported_semantic_artifacts"] >= 3
    assert replay["imported_semantic_artifacts"] == 0
    assert replayed_job_artifact["payload_hash"] == job_artifact["payload_hash"]
    assert (
        replayed_job_artifact["source_recorded_at"]
        == job_artifact["source_recorded_at"]
    )


def test_first_backfill_rejects_coordinated_approval_ledger_removal(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)

    def _effect(**kwargs):
        job = _matching_validation_job(deps, approved["action"])
        return {"validation_job_id": job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_runs
        SET harness_id = 'harness.default', trace_id = 'trace-deleted-approval'
        WHERE id = ?
        """,
        (run["id"],),
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TRIGGER approval_events_no_delete")
    conn.execute("DROP TRIGGER approval_commands_no_delete")
    conn.execute("DROP TRIGGER approval_records_no_delete")
    conn.execute(
        "DELETE FROM approval_events WHERE tenant_id = ? AND workflow_id = ?",
        ("client-a", run["id"]),
    )
    conn.execute(
        "DELETE FROM approval_commands WHERE tenant_id = ? AND workflow_id = ?",
        ("client-a", run["id"]),
    )
    conn.execute(
        "DELETE FROM approval_records WHERE tenant_id = ? AND workflow_id = ?",
        ("client-a", run["id"]),
    )
    conn.commit()

    with pytest.raises(ValueError, match="approval history is unavailable"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id="client-a", run_id=run["id"]
        )

    assert (
        conn.execute(
            """
            SELECT 1 FROM workflow_compatibility_semantic_status
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            ("client-a", run["id"]),
        ).fetchone()
        is None
    )


def test_first_backfill_rejects_coordinated_effect_bundle_removal(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    created_job = None

    def _effect(**kwargs):
        nonlocal created_job
        created_job = _matching_validation_job(deps, approved["action"])
        return {"validation_job_id": created_job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")
    assert created_job is not None
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_runs
        SET harness_id = 'harness.default', trace_id = 'trace-deleted-effect'
        WHERE id = ?
        """,
        (run["id"],),
    )
    conn.commit()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TRIGGER approval_effect_executions_no_delete")
    conn.execute(
        "DELETE FROM validation_results WHERE job_id = ?", (created_job["id"],)
    )
    conn.execute("DELETE FROM validation_jobs WHERE id = ?", (created_job["id"],))
    conn.execute(
        "DELETE FROM approval_effect_executions WHERE workflow_id = ?",
        (run["id"],),
    )
    conn.commit()

    with pytest.raises(ValueError, match="effect bundle is unavailable"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id="client-a", run_id=run["id"]
        )

    assert (
        conn.execute(
            """
            SELECT 1 FROM workflow_compatibility_semantic_status
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            ("client-a", run["id"]),
        ).fetchone()
        is None
    )


def test_first_backfill_rejects_a_missing_historical_completion_decision(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    governed, service = _commit_initial_incomplete_decision(deps, run, actions[0])
    governed.agent_runs.update_agent_run(run_id=run["id"], status="running")
    service.evaluate_and_commit_lifecycle(
        command=replace(
            outcome_command(
                run["id"],
                command_id="semantic-decision-b",
                issued_at=NOW + timedelta(minutes=60),
            ),
            tenant_id=TENANT_ID,
        ),
        snapshot_id="semantic-snapshot-a",
        decision_id="semantic-decision-b",
        evaluated_at=NOW + timedelta(minutes=55),
    )
    conn = get_connection()
    assert (
        conn.execute(
            """
            SELECT current_sequence FROM workflow_completion_event_cursors
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            (TENANT_ID, run["id"]),
        ).fetchone()["current_sequence"]
        == 1
    )
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TRIGGER workflow_completion_lifecycle_events_no_delete")
    conn.execute("DROP TRIGGER workflow_completion_decisions_no_delete")
    conn.execute("DROP TRIGGER workflow_outcome_commands_no_delete")
    conn.execute(
        """
        DELETE FROM workflow_completion_lifecycle_events
        WHERE tenant_id = ? AND workflow_id = ?
          AND authoritative_event_sequence = 0
        """,
        (TENANT_ID, run["id"]),
    )
    conn.execute(
        "DELETE FROM workflow_completion_decisions WHERE decision_id = ?",
        ("semantic-decision-a",),
    )
    conn.execute(
        "DELETE FROM workflow_outcome_commands WHERE command_id = ?",
        ("semantic-decision",),
    )
    conn.commit()

    with pytest.raises(ValueError, match="lifecycle history is incomplete"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id=TENANT_ID,
            run_id=run["id"],
        )

    assert (
        conn.execute(
            """
            SELECT 1 FROM workflow_compatibility_semantic_status
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            (TENANT_ID, run["id"]),
        ).fetchone()
        is None
    )
