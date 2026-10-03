"""Durable cancellation survives background lifecycle writers and late snapshots."""

import sqlite3

import pytest

from api.runtime_composition import default_completion_coordinator, default_runtime
from application.services.agent_runtime import governed_runs
from application.services.agent_runtime.runtime import NoApprovedActionError
from application.services.agent_runtime.runtime import service as runtime_service
from application.services.agent_runtime.worker import AgentRuntimeWorkerService
from infrastructure.db.core.connection import get_connection
from shared.db.migrations import apply_migrations
from tests.modules.test_operator_conversation_cancel import (
    cancel_api as _cancel_api_fixture,
    confirm_cancel,
    eligible_run,
    propose_cancel,
)
from tests.modules.test_operator_resume_admission_integrity import governed_run
from test_operator_conversation_api import TENANT, USER, _action


@pytest.fixture
def cancel_api(tmp_path, monkeypatch):
    yield from _cancel_api_fixture.__wrapped__(tmp_path, monkeypatch)


def cancel(client, run):
    proposal = propose_cancel(client, run)
    response = confirm_cancel(client, run, proposal)
    assert response.status_code == 200, response.text
    return proposal, response.json()["receipt"]


def assert_terminal(client, deps, run, proposal, receipt):
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "canceled"
    assert all(
        item["id"] != run["id"]
        for item in deps.agent_runs.list_runnable_agent_runs(client_id=TENANT)
    )
    replay = confirm_cancel(client, run, proposal)
    assert replay.status_code == 200, replay.text
    assert replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    assert (
        len(
            [
                e
                for e in deps.agent_events.list_agent_events(agent_run_id=run["id"])
                if e["event_type"] == "run_canceled"
            ]
        )
        == 1
    )


@pytest.mark.parametrize("governed", [False, True])
@pytest.mark.parametrize(
    "status",
    ["planned", "running", "paused", "failed", "completed", "cancelled", "CANCELED"],
)
def test_persistence_rejects_every_status_overwrite(cancel_api, governed, status):
    client, deps = cancel_api
    run = governed_run(deps) if governed else eligible_run(deps)
    proposal, receipt = cancel(client, run)
    with pytest.raises(
        sqlite3.IntegrityError,
        match="terminal run status is immutable|canceled run status is immutable",
    ):
        deps.agent_runs.update_agent_run(
            run_id=run["id"], status=status, state="overwritten"
        )
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["state"] == run["state"]
    assert_terminal(client, deps, run, proposal, receipt)


def test_reconciliation_after_worker_lock_release_preserves_cancel(
    cancel_api, monkeypatch
):
    client, deps = cancel_api
    run = eligible_run(deps, status="running")
    _action(deps, run["id"])
    worker = AgentRuntimeWorkerService(deps=deps)
    step = worker._runtime.step_once
    evidence = []

    def cancel_after_release(**kwargs):
        try:
            return step(**kwargs)
        except NoApprovedActionError:
            assert deps.agent_runs.get_agent_run(run_id=run["id"])["lock_token"] is None
            evidence.append(cancel(client, run))
            raise

    monkeypatch.setattr(worker._runtime, "step_once", cancel_after_release)
    result = worker.tick_client(client_id=TENANT, user_id=USER)
    assert result["results"][0]["status"] == "canceled"
    assert result["steps_executed_total"] == 0
    assert_terminal(client, deps, run, *evidence[0])


def test_cancellation_between_reconciliation_read_and_write_wins(
    cancel_api, monkeypatch
):
    client, deps = cancel_api
    run = eligible_run(deps, status="running")
    _action(deps, run["id"])
    compute = runtime_service.compute_next_run_status
    evidence = []

    def cancel_after_derivation(**kwargs):
        status = compute(**kwargs)
        assert status == "planned"
        evidence.append(cancel(client, run))
        return status

    monkeypatch.setattr(
        runtime_service, "compute_next_run_status", cancel_after_derivation
    )
    result = default_runtime(deps).reconcile_run_status(run_id=run["id"])
    assert result.run["status"] == "canceled"
    assert_terminal(client, deps, run, *evidence[0])


@pytest.mark.parametrize("fails", [False, True])
@pytest.mark.parametrize("release", [False, True])
def test_cancel_during_activation_fences_release_and_failure_handler(
    cancel_api, monkeypatch, fails, release
):
    client, deps = cancel_api
    run = eligible_run(deps, status="planning")
    _action(deps, run["id"])
    # Enter the production activation boundary after a persisted initial plan.
    monkeypatch.setattr(
        governed_runs, "create_agent_run_with_initial_plan", lambda **kwargs: run
    )
    coordinator = default_completion_coordinator(deps)
    evidence = []

    class CancellingCoordinator:
        def activate_run(self, *, run_id):
            governed = coordinator.activate_run(run_id=run_id) if not fails else None
            evidence.append(cancel(client, run))
            if fails:
                raise RuntimeError("activation failed after cancellation")
            return governed

    if fails:
        with pytest.raises(RuntimeError, match="activation failed after cancellation"):
            governed_runs.create_governed_agent_run_with_initial_plan(
                deps=deps,
                completion_coordinator=CancellingCoordinator(),
                release_to_planned=release,
            )
    else:
        result = governed_runs.create_governed_agent_run_with_initial_plan(
            deps=deps,
            completion_coordinator=CancellingCoordinator(),
            release_to_planned=release,
        )
        assert result["status"] == "canceled"
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["error"] is None
    assert_terminal(client, deps, run, *evidence[0])


def test_additive_guard_protects_existing_058_receipt(cancel_api):
    client, deps = cancel_api
    conn = get_connection()
    conn.execute("DROP TRIGGER operator_canceled_run_terminal_guard")
    conn.execute(
        "DELETE FROM schema_migrations WHERE name = '059_operator_cancel_terminal_guard.sql'"
    )
    conn.commit()
    run = eligible_run(deps)
    proposal, receipt = cancel(client, run)
    before = tuple(conn.execute("SELECT * FROM operator_cancel_receipts").fetchone())
    apply_migrations(conn)
    assert (
        tuple(conn.execute("SELECT * FROM operator_cancel_receipts").fetchone())
        == before
    )
    with pytest.raises(
        sqlite3.IntegrityError, match="operator canceled run status is immutable"
    ):
        conn.execute(
            "UPDATE agent_runs SET status = 'planned' WHERE id = ?", (run["id"],)
        )
    conn.rollback()
    # Housekeeping and idempotent canceled writes remain available.
    assert deps.agent_runs.acquire_run_lock(run_id=run["id"], lock_token="late-worker")
    assert deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="late-worker")
    deps.agent_runs.update_agent_run(run_id=run["id"], status="canceled")
    assert_terminal(client, deps, run, proposal, receipt)
