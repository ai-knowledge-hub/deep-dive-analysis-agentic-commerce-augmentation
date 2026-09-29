import sqlite3

import pytest

from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.commands.recovery import (
    create_change_plan_recovery_action,
    create_retry_action,
)
from application.services.agent_runtime.effect_recovery import (
    reconcile_effect_from_durable_evidence,
)
from application.services.agent_runtime.runtime import AgentRuntimeService
from application.services.conversation.operator_snapshot import build_operator_snapshot
from application.services.validation_service import ValidationService
from shared.db.connection import get_connection
from tests.modules.approval_effect_support import matching_validation_job
from tests.modules.test_approval_effect_authorization import _approve, _run_and_action


def test_runtime_validation_link_is_canonical_and_legacy_output_is_verified(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    observed_job_id = None

    def _effect(**_kwargs):
        nonlocal observed_job_id
        job = matching_validation_job(deps, approved["action"])
        observed_job_id = job["id"]
        return {"validation_job_id": observed_job_id}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )

    assert result.action["validation_job_id"] == observed_job_id
    snapshot = _snapshot(deps, run["id"])
    assert [job["id"] for job in snapshot["validation_jobs"]] == [observed_job_id]
    assert snapshot["completeness"]["validation_jobs"] == {
        "state": "complete",
        "requested_count": 1,
        "included_count": 1,
        "missing_count": 0,
        "unavailable_count": 0,
        "contradictory_count": 0,
    }

    # Simulate the output-only representation written before the canonical
    # action-column link was added to the effect-completion transaction.
    get_connection().execute(
        "UPDATE agent_actions SET validation_job_id = NULL WHERE id = ?",
        (action["id"],),
    )
    get_connection().commit()

    legacy_snapshot = _snapshot(deps, run["id"])
    assert [job["id"] for job in legacy_snapshot["validation_jobs"]] == [
        observed_job_id
    ]


@pytest.mark.parametrize("reconcile_after_commit_failure", [False, True])
def test_validation_retry_commits_its_own_job_and_can_reconcile(
    tmp_path, monkeypatch, reconcile_after_commit_failure
):
    deps, run, action, _ = _run_and_action(tmp_path)
    source_job = _unbound_validation_job(deps, action)
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_actions
        SET status = 'failed', validation_job_id = ?, error_text = 'retry requested'
        WHERE id = ?
        """,
        (source_job["id"], action["id"]),
    )
    conn.commit()
    failed_run = deps.agent_runs.update_agent_run(
        run_id=run["id"], status="failed", error="retry requested"
    )
    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])

    retry = create_retry_action(
        deps=deps,
        run_id=run["id"],
        run=failed_run,
        action=failed_action,
        metadata={"retry_strategy": "same_action"},
    )

    assert retry["validation_job_id"] is None
    assert retry["inputs"]["recovery_context"]["source_validation_job_id"] == (
        source_job["id"]
    )
    approved_retry = _approve(deps, failed_run, retry)["action"]
    deps.agent_runs.update_agent_run(run_id=run["id"], status="planned", error=None)
    observed_job = None

    def _effect(**_kwargs):
        nonlocal observed_job
        observed_job = matching_validation_job(deps, approved_retry)
        return {"validation_job_id": observed_job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    original_commit = deps.approval_ledger.commit_effect_completion
    if reconcile_after_commit_failure:
        def _fail_commit(**_kwargs):
            raise sqlite3.IntegrityError("simulated post-effect receipt failure")

        monkeypatch.setattr(
            deps.approval_ledger,
            "commit_effect_completion",
            _fail_commit,
        )
        with pytest.raises(CapabilityExecutionError, match="post-effect"):
            AgentRuntimeService(deps=deps).step_once(
                run_id=run["id"], user_id="operator-a"
            )
        uncertain = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id="client-a", workflow_id=run["id"], action_id=retry["id"]
        )
        assert uncertain["status"] == "uncertain"
        assert deps.agent_actions.get_agent_action(action_id=retry["id"])[
            "validation_job_id"
        ] is None
        monkeypatch.setattr(
            deps.approval_ledger, "commit_effect_completion", original_commit
        )
        final = reconcile_effect_from_durable_evidence(
            deps=deps,
            run=deps.agent_runs.get_agent_run(run_id=run["id"]),
            action=deps.agent_actions.get_agent_action(action_id=retry["id"]),
        )["action"]
    else:
        final = AgentRuntimeService(deps=deps).step_once(
            run_id=run["id"], user_id="operator-a"
        ).action

    assert observed_job["id"] != source_job["id"]
    assert deps.agent_actions.get_agent_action(action_id=action["id"])[
        "validation_job_id"
    ] == source_job["id"]
    assert final["validation_job_id"] == observed_job["id"]
    assert final["outputs"]["validation_job_id"] == observed_job["id"]
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=retry["id"]
    )
    assert effect["status"] == "succeeded"
    assert effect["receipt_id"] == f"validation-job:{observed_job['id']}"


def test_change_plan_keeps_source_job_as_context_not_result(tmp_path):
    deps, run, action, _ = _run_and_action(tmp_path)
    source_job = _unbound_validation_job(deps, action)
    conn = get_connection()
    conn.execute(
        "UPDATE agent_actions SET status = 'failed', validation_job_id = ? WHERE id = ?",
        (source_job["id"], action["id"]),
    )
    conn.commit()
    failed_run = deps.agent_runs.update_agent_run(
        run_id=run["id"], status="failed", error="change requested"
    )
    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])

    recovery = create_change_plan_recovery_action(
        deps=deps,
        run_id=run["id"],
        run=failed_run,
        source_action=failed_action,
        command_receipt={"id": "change-plan-validation"},
        message=None,
        metadata={
            "capability_name": "request_synthetic_validation",
            "inputs": {
                "recovery_context": {
                    "source_validation_job_id": "forged-browser-job"
                }
            },
        },
    )

    assert recovery["validation_job_id"] is None
    assert "validation_job_id" not in recovery["inputs"]
    assert recovery["inputs"]["recovery_context"][
        "source_validation_job_id"
    ] == source_job["id"]
    event = deps.agent_events.list_agent_events(
        agent_run_id=run["id"], event_type="action_recovery_proposed", limit=1
    )[0]
    assert event["anchors"]["validation_job_id"] is None
    assert event["anchors"]["source_validation_job_id"] == source_job["id"]


def _unbound_validation_job(deps, action):
    return ValidationService(deps=deps).create_job(
        client_id="client-a",
        entity_type="experiment_run",
        entity_id=action["inputs"]["experiment_id"],
        provider="openrouter",
        mode="manual_fallback",
        input_payload={"source": "previous-attempt"},
        requested_by="operator-a",
    )


def _snapshot(deps, run_id: str):
    return build_operator_snapshot(
        deps=deps,
        completion_reader=lambda **_kwargs: None,
        tenant_id="client-a",
        principal_id="human:operator-a",
        run_id=run_id,
    )
