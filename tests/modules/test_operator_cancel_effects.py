"""Cancellation must compose with the existing exact approval and effect boundary."""

from __future__ import annotations

import pytest

from api.runtime_composition import default_completion_coordinator
from api.utils.principals import ensure_principal
from application.services.conversation.operator_gateway import (
    OperatorConversationService,
)
from application.services.conversation.operator_cancel import (
    build_cancel_snapshot,
    conversational_cancel_preflight,
)
from application.services.agent_runtime.runtime import (
    AgentRuntimeService,
    AgentRuntimeError,
)
from tests.modules.test_approval_effect_authorization import (
    _run_and_action,
    _approve,
    _commit_effect,
)
from tests.modules.approval_effect_support import matching_validation_job
from application.services.agent_runtime.approval_authorization import (
    mark_authorized_effect_uncertain,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from shared.db.connection import get_connection


def prepare(tmp_path, *, status="proposed"):
    deps, run, action, spec = _run_and_action(tmp_path, status=status)
    deps.users.ensure_user("operator-a")
    deps.clients.add_client_user(
        client_id="client-a", user_id="operator-a", role="operator"
    )
    ensure_principal(
        principal_id="human:operator-a", principal_type="human", tenant_id="client-a"
    )
    return deps, run, action, spec


def proposal(deps, run):
    return OperatorConversationService(
        deps=deps,
        completion_reader=default_completion_coordinator(
            deps
        ).get_completion_read_model,
    ).respond(
        tenant_id="client-a",
        principal_id="human:operator-a",
        session_user_id="operator-a",
        run_id=run["id"],
        message="Cancel this run",
    )["command_proposal"]


def commit(deps, run, view):
    canonical = {k: v for k, v in view.items() if k != "consequences"}

    def confirmation_state():
        snapshot = build_cancel_snapshot(
            deps=deps,
            completion_reader=default_completion_coordinator(
                deps
            ).get_completion_read_model,
            tenant_id="client-a",
            principal_id="human:operator-a",
            run_id=run["id"],
        )
        return {
            "snapshot_digest": snapshot["snapshot_digest"],
            "preflight": conversational_cancel_preflight(
                deps=deps, tenant_id="client-a", run_id=run["id"], snapshot=snapshot
            ),
        }

    return deps.operator_commands.commit_cancel(
        proposal=canonical,
        principal_id="human:operator-a",
        confirmation_state=confirmation_state,
    )


def pause(deps, run):
    return deps.agent_runs.update_agent_run(run_id=run["id"], status="paused")


@pytest.mark.parametrize("state", ["started", "uncertain"])
def test_cancel_blocks_unreconciled_effect_even_without_runtime_lock(tmp_path, state):
    deps, run, action, spec = prepare(tmp_path)
    _approve(deps, run, action)
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, action, spec)
    if state == "uncertain":
        mark_authorized_effect_uncertain(
            deps=deps,
            run=run,
            action=action,
            authorization=authorization,
            error_code="provider_unknown",
        )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    pause(deps, run)
    assert proposal(deps, run) is None
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    assert effect["status"] == state


def test_cancel_does_not_manufacture_action_approval(tmp_path, monkeypatch):
    deps, run, action, spec = prepare(tmp_path, status="approved")
    pause(deps, run)
    view = proposal(deps, run)
    assert view is not None
    commit(deps, run, view)
    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **_: pytest.fail("Cancellation executed a capability"),
    )
    with pytest.raises(AgentRuntimeError, match="not executable"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")
    assert (
        deps.approval_ledger.get_effect_execution_for_action(
            tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
        )
        is None
    )


def test_cancel_preserves_committed_effect_and_fulfilled_approval(
    tmp_path, monkeypatch
):
    deps, run, action, spec = prepare(tmp_path)
    _approve(deps, run, action)
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    _commit_effect(deps, run, action, spec)
    job = matching_validation_job(deps, action)
    outputs = {"validation_job_id": job["id"]}
    reconciled = reconcile_authorized_effect(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=f"validation-job:{job['id']}",
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    pause(deps, run)
    view = proposal(deps, run)
    assert view is not None
    commit(deps, run, view)
    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **_: pytest.fail("Committed effect repeated"),
    )
    with pytest.raises(AgentRuntimeError, match="not executable"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    assert effect == reconciled
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "canceled"
    assert (
        deps.approval_ledger.get_current_approval_for_action(
            tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
        )["status"]
        == "fulfilled"
    )


@pytest.mark.parametrize(
    "change", ["approval", "effect", "validation_result", "validation_job"]
)
def test_cancel_fences_full_approval_effect_and_validation_evidence(tmp_path, change):
    from domain.workflow.operator_commands import OperatorCommandConflictError

    deps, run, action, spec = prepare(tmp_path)
    _approve(deps, run, action)
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    _commit_effect(deps, run, action, spec)
    job = matching_validation_job(deps, action)
    outputs = {"validation_job_id": job["id"]}
    reconcile_authorized_effect(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=f"validation-job:{job['id']}",
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    pause(deps, run)
    view = proposal(deps, run)
    conn = get_connection()
    # Mutable compatibility state must still be fenced even if no timestamp changes.
    queries = {
        "approval": (
            "UPDATE approval_records SET updated_at = 'changed' WHERE action_id = ?",
            (action["id"],),
        ),
        "effect": (
            "UPDATE approval_effect_executions SET completed_at = 'changed' WHERE action_id = ?",
            (action["id"],),
        ),
        "validation_result": (
            "UPDATE validation_results SET score = 0.1 WHERE job_id = ?",
            (job["id"],),
        ),
        "validation_job": (
            "UPDATE validation_jobs SET status = 'failed' WHERE id = ?",
            (job["id"],),
        ),
    }
    if change == "effect":
        from tests.modules.test_approval_effect_authorization import _additional_action

        second = _additional_action(deps, run, spec)
        _approve(deps, run, second)
        second = deps.agent_actions.transition_agent_action_status(
            action_id=second["id"], from_status="approved", to_status="executing"
        )
        _commit_effect(deps, run, second, spec)
        deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
        pause(deps, run)
    else:
        conn.execute(*queries[change])
        conn.commit()
    with pytest.raises(OperatorCommandConflictError, match="evidence changed"):
        commit(deps, run, view)
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"


def test_cancel_fences_late_worker_at_pre_effect_commit(tmp_path):
    from application.services.agent_runtime.approval_authorization import (
        commit_pre_effect_authorization,
        ApprovalAuthorizationError,
    )

    deps, run, action, spec = prepare(tmp_path)
    _approve(deps, run, action)
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    # A stale worker retains this valid action and approval after recovery makes
    # control state quiescent. Cancellation must still stop its final effect commit.
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="approved"
    )
    pause(deps, run)
    commit(deps, run, proposal(deps, run))
    assert deps.agent_runs.acquire_run_lock(
        run_id=run["id"], lock_token="late-worker", ttl_seconds=30
    )
    with pytest.raises(ApprovalAuthorizationError):
        commit_pre_effect_authorization(
            deps=deps,
            run=run,
            action=action,
            spec=spec,
            executable_inputs=action["inputs"],
            lock_token="late-worker",
        )
    assert (
        deps.approval_ledger.get_effect_execution_for_action(
            tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
        )
        is None
    )
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "canceled"
