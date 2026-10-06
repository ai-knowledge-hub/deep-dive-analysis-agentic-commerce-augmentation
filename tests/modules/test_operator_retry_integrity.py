"""Effects, commit faults, replay, migrations and final-lock retry fences."""

import dataclasses
import sqlite3

import pytest

from api.main import app
from api.routes import operator_conversation
from api.runtime_composition import default_completion_coordinator
from application.services.agent_runtime.approval_authorization import (
    mark_authorized_effect_uncertain,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from infrastructure.db.core.connection import get_connection
from tests.modules.test_approval_effect_authorization import _commit_effect
from tests.modules.test_operator_retry import (
    retry_api as _fixture,
    source,
    propose,
    confirm,
    assert_no_retry,
)
from tests.modules.test_operator_action_review import (
    review_run,
    propose as propose_review,
    confirm as confirm_review,
)
from test_operator_conversation_api import TENANT, USER, _post, _bff_headers


@pytest.fixture
def retry_api(tmp_path, monkeypatch):
    yield from _fixture.__wrapped__(tmp_path, monkeypatch)


def validation_job(deps, action):
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=action["agent_run_id"], action_id=action["id"]
    )
    inputs = action["inputs"]
    job = deps.validation_jobs.create_job(
        client_id=TENANT,
        brand_id=None,
        product_id=None,
        entity_type="experiment_run",
        entity_id=inputs["experiment_id"],
        provider=inputs["provider"],
        mode=inputs["mode"],
        model=inputs.get("model"),
        prompt_version=inputs["prompt_version"],
        status="completed",
        integration_type=None,
        provider_run_id=None,
        callback_verified=False,
        agent_action_id=action["id"],
        approval_id=effect["approval_id"],
        effect_idempotency_key=effect["effect_idempotency_key"],
        approval_effect_execution_id=effect["execution_id"],
        input_payload={"source": "retry-test"},
        requested_by=USER,
    )
    deps.validation_results.create_result(
        job_id=job["id"],
        provider=job["provider"],
        model=job["requested_model"],
        structured_result={"winner_id": "variant-a", "score": 0.9},
        raw_response=None,
        score=0.9,
        winner_id="variant-a",
        evidence_strength="strong",
        latency_ms=10,
        cost_usd=None,
        source="synthetic",
        callback_verified=False,
    )
    return job


def started_source(retry_api, tmp_path):
    client, deps, run, action, spec = review_run(retry_api, tmp_path)
    review = propose_review(client, run, action)
    assert confirm_review(client, run, review).status_code == 200
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, action, spec)
    assert authorization is not None
    return client, deps, run, action, spec, authorization


@pytest.mark.parametrize("state", ["started", "uncertain", "succeeded"])
def test_durable_source_effect_prevents_retry_even_with_failed_projection(
    retry_api, tmp_path, state
):
    client, deps, run, action, spec, auth = started_source(retry_api, tmp_path)
    if state == "uncertain":
        mark_authorized_effect_uncertain(
            deps=deps,
            run=run,
            action=action,
            authorization=auth,
            error_code="provider_timeout",
        )
    if state == "succeeded":
        job = validation_job(deps, action)
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
    action = deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", outputs={}
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    deps.agent_runs.update_agent_run(run_id=run["id"], status="planned")
    result = _post(client, run["id"], message=f"Retry action {action['id']}")
    assert result.status_code == 200 and result.json()["command_proposal"] is None
    assert "effect" in result.json()["answer"].lower()
    assert len(deps.agent_actions.list_agent_actions(agent_run_id=run["id"])) == 1
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_retry_receipts")
        .fetchone()[0]
        == 0
    )


def test_legacy_retry_child_cannot_hide_ancestor_effect(retry_api, tmp_path):
    from application.services.agent_runtime.commands.recovery import create_retry_action

    client, deps, run, action, _, _ = started_source(retry_api, tmp_path)
    action = deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed"
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    child = create_retry_action(
        deps=deps,
        run_id=run["id"],
        run=run,
        action=action,
        metadata={"retry_strategy": "same_action"},
    )
    deps.agent_actions.update_agent_action_status(
        action_id=child["id"], status="failed"
    )
    deps.agent_runs.update_agent_run(run_id=run["id"], status="planned")
    assert (
        _post(client, run["id"], message=f"Retry action {child['id']}").json()[
            "command_proposal"
        ]
        is None
    )
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_retry_receipts")
        .fetchone()[0]
        == 0
    )


def test_final_commit_error_is_preserved_and_later_writer_cannot_commit_retry(
    retry_api, tmp_path, monkeypatch
):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    conn = get_connection()
    error = sqlite3.OperationalError("injected retry commit failure")

    class FailCommit:
        def __getattr__(self, name):
            return getattr(conn, name)

        def commit(self):
            raise error

    monkeypatch.setattr(
        "infrastructure.db.agent.operator_retries.get_connection", lambda: FailCommit()
    )
    from types import SimpleNamespace
    from application.services.conversation.operator_retry import confirm_retry

    with pytest.raises(sqlite3.OperationalError) as caught:
        confirm_retry(
            deps=deps,
            proposal=deps.operator_commands.get_proposal(
                proposal_id=proposal["proposal_id"],
                tenant_id=TENANT,
                workflow_id=run["id"],
            ),
            authority=SimpleNamespace(principal_id=f"human:{USER}"),
            completion_reader=default_completion_coordinator(
                deps
            ).get_completion_read_model,
            require_access=lambda: None,
        )
    assert caught.value is error
    assert not conn.in_transaction
    deps.users.ensure_user("unrelated-later-writer")
    assert_no_retry(deps, run, action)


def test_workflow_dual_write_fault_rolls_back_child_and_receipt(retry_api, tmp_path):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    conn = get_connection()
    conn.execute(
        "UPDATE agent_runs SET harness_id = 'operator_supervised', trace_id = 'retry-trace' WHERE id = ?",
        (run["id"],),
    )
    conn.commit()
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT, run_id=run["id"]
    )
    proposal = propose(client, run, action)
    conn.execute(
        "CREATE TRIGGER retry_projection_fault BEFORE INSERT ON workflow_compatibility_events BEGIN SELECT RAISE(ABORT, 'projection write fault'); END"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="projection write fault"):
        confirm(client, run, proposal)
    assert_no_retry(deps, run, action)
    assert (
        conn.execute("SELECT count(*) FROM workflow_compatibility_events").fetchone()[0]
        == 0
    )


def test_cancellation_wins_and_successful_retry_replay_survives_cancellation(
    retry_api, tmp_path
):
    from tests.modules.test_operator_conversation_cancel import (
        propose_cancel,
        confirm_cancel,
    )

    client, deps, run, action, _ = source(retry_api, tmp_path)
    first = propose(client, run, action)
    result = confirm(client, run, first)
    assert result.status_code == 200
    second = propose(client, run, action)
    cancel = propose_cancel(client, run)
    assert confirm_cancel(client, run, cancel).status_code == 200
    assert confirm(client, run, second).status_code == 409
    replay = confirm(client, run, first)
    assert (
        replay.status_code == 200
        and replay.json()["receipt"]["receipt_digest"]
        == result.json()["receipt"]["receipt_digest"]
    )
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "canceled"
    assert len(deps.agent_actions.list_agent_actions(agent_run_id=run["id"])) == 2
    conn = get_connection()
    conn.execute(
        "UPDATE client_users SET role = 'analyst' WHERE client_id = ? AND user_id = ?",
        (TENANT, USER),
    )
    conn.commit()
    assert confirm(client, run, first).status_code == 403


@pytest.mark.parametrize("change", ["completion", "registry", "validation"])
def test_changes_between_route_read_and_final_lock_block_retry(
    retry_api, tmp_path, monkeypatch, change
):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    store = deps.operator_commands
    coordinator = default_completion_coordinator(deps)
    read = coordinator.get_completion_read_model
    changed = {"value": False}
    monkeypatch.setattr(
        coordinator,
        "get_completion_read_model",
        lambda **scope: None if changed["value"] else read(**scope),
    )

    class Race:
        def __getattr__(self, name):
            return getattr(store, name)

        def commit_retry(self, **kwargs):
            if change == "completion":
                changed["value"] = True
            elif change == "registry":
                monkeypatch.setattr(
                    "application.services.conversation.operator_retry.registry_contract_payload",
                    lambda: {"registry_version": "changed"},
                )
            else:
                conn = get_connection()
                conn.execute(
                    'UPDATE agent_actions SET outputs_json = \'{"validation_job_id":"missing-job"}\' WHERE id = ?',
                    (action["id"],),
                )
                conn.commit()
            return store.commit_retry(**kwargs)

    app.dependency_overrides[operator_conversation._deps] = lambda: dataclasses.replace(
        deps, operator_commands=Race()
    )
    app.dependency_overrides[operator_conversation._completion_coordinator] = lambda: (
        coordinator
    )
    assert confirm(client, run, proposal).status_code == 409
    assert_no_retry(
        deps, run, deps.agent_actions.get_agent_action(action_id=action["id"])
    )


def test_read_assertion_cannot_confirm_retry(retry_api, tmp_path):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_bff_headers(run_id=run["id"]),
        json={
            "client_id": TENANT,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": "retry",
            "action_id": action["id"],
            "retry_strategy": "same_action",
        },
    )
    assert response.status_code == 401
    assert_no_retry(deps, run, action)


@pytest.mark.parametrize(
    "table", ["operator_retry_proposals", "operator_retry_receipts", "agent_events"]
)
@pytest.mark.parametrize("operation", ["update", "delete", "replace"])
def test_retry_and_audits_are_immutable(retry_api, tmp_path, table, operation):
    client, _, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    conn = get_connection()
    key = "id" if table == "agent_events" else "proposal_id"
    identity = (
        receipt["event_ids"]["lifecycle"]
        if table == "agent_events"
        else proposal["proposal_id"]
    )
    row = conn.execute(f"SELECT * FROM {table} WHERE {key} = ?", (identity,)).fetchone()
    with pytest.raises(sqlite3.IntegrityError):
        if operation == "update":
            conn.execute(
                f"UPDATE {table} SET {key} = ? WHERE {key} = ?",
                ("substituted", identity),
            )
        elif operation == "delete":
            conn.execute(f"DELETE FROM {table} WHERE {key} = ?", (identity,))
        else:
            columns = [r["name"] for r in conn.execute(f"PRAGMA table_info({table})")]
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({', '.join(columns)}) VALUES ({', '.join('?' for _ in columns)})",
                [row[c] for c in columns],
            )
    conn.rollback()
    assert (
        confirm(client, run, proposal).json()["receipt"]["receipt_digest"]
        == receipt["receipt_digest"]
    )


def test_retry_child_requires_fresh_approval_and_worker_consumes_its_effect_once(
    retry_api, tmp_path, monkeypatch
):
    from api.runtime_composition import default_worker

    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200
    receipt = response.json()["receipt"]
    child = deps.agent_actions.get_agent_action(action_id=receipt["action_id"])
    calls = []

    def execute_capability(**_):
        current = deps.agent_actions.get_agent_action(action_id=child["id"])
        effect = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=TENANT, workflow_id=run["id"], action_id=child["id"]
        )
        assert effect and effect["status"] == "started"
        assert effect["effect_idempotency_key"] == receipt["effect_idempotency_key"]
        calls.append(effect["execution_id"])
        job = validation_job(deps, current)
        return {
            "validation_job_id": job["id"],
            "provider": job["provider"],
            "mode": job["mode"],
            "status": "completed",
        }

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        execute_capability,
    )
    worker = default_worker(deps)
    first = worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=1)
    assert first["steps_executed_total"] == 0 and calls == []
    assert (
        deps.agent_actions.get_agent_action(action_id=child["id"])["status"]
        == "proposed"
    )
    # Synchronization may update completion evidence; request approval afresh.
    run = deps.agent_runs.get_agent_run(run_id=run["id"])
    review = propose_review(client, run, child)
    approved = confirm_review(client, run, review)
    assert approved.status_code == 200, approved.text
    result = worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=1)
    assert result["steps_executed_total"] == 1, result
    assert len(calls) == 1
    assert (
        deps.agent_actions.get_agent_action(action_id=child["id"])["status"]
        == "executed"
    )
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action
    worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=1)
    assert len(calls) == 1
    # Recovering a child does not manufacture success for its failed source.
    completion = default_completion_coordinator(deps).get_completion_read_model(
        tenant_id=TENANT, workflow_id=run["id"]
    )
    assert completion["authoritative_decision"]["status"] != "COMPLETE"
    assert (
        confirm(client, run, proposal).json()["receipt"]["receipt_digest"]
        == receipt["receipt_digest"]
    )


def test_migration_061_preserves_previous_contracts_and_cursor_replay(
    retry_api, tmp_path
):
    from shared.db.migrations import apply_migrations
    from tests.modules.test_operator_conversation_cancel import (
        eligible_run,
        propose_cancel,
        confirm_cancel,
    )
    from tests.modules.test_operator_conversation_resume import (
        propose as propose_resume,
        confirm as confirm_control,
    )

    client, deps, run, action, _ = source(retry_api, tmp_path)
    old_run = eligible_run(deps)
    resume = propose_resume(client, old_run)
    assert confirm_control(client, old_run, resume).status_code == 200
    pause = _post(client, old_run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert (
        confirm_control(client, old_run, pause, command_type="pause").status_code == 200
    )
    cancel = propose_cancel(client, old_run)
    assert confirm_cancel(client, old_run, cancel).status_code == 200
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="proposed"
    )
    old_review = propose_review(client, run, action)
    assert confirm_review(client, run, old_review).status_code == 200
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed"
    )
    conn = get_connection()
    tables = [
        f"operator_{stem}_{kind}"
        for stem in ("command", "resume", "cancel", "action_review")
        for kind in ("proposals", "receipts")
    ]
    before = {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
        for table in tables
    }
    cursor = deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=old_run["id"], limit=1
    )["page"]["next_cursor"]
    conn.executescript(
        "DROP VIEW operator_all_receipts_v5; DROP VIEW operator_all_proposals_v5; DROP TRIGGER operator_retry_audit_no_update; DROP TRIGGER operator_retry_audit_no_delete; DROP TRIGGER operator_retry_audit_no_replace; DROP TABLE operator_retry_receipts; DROP TABLE operator_retry_proposals; DELETE FROM schema_migrations WHERE name = '061_operator_conversation_retry_proposals.sql';"
    )
    apply_migrations(conn)
    assert {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
        for table in tables
    } == before
    assert deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=old_run["id"], limit=1, cursor=cursor
    )["records"]
    assert confirm_review(client, run, old_review).json()["receipt"]["replayed"]
    retry = propose(client, run, action)
    response = confirm(client, run, retry)
    assert response.status_code == 200, response.text
    assert (
        conn.execute("SELECT count(*) FROM operator_all_receipts_v4").fetchone()[0] == 4
    )
    assert (
        conn.execute("SELECT count(*) FROM operator_all_receipts_v5").fetchone()[0] == 5
    )


def test_receipt_verifies_in_fresh_process_after_source_state_changes(
    retry_api, tmp_path
):
    import subprocess
    import sys
    from shared.db import connection

    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="rejected"
    )
    program = "from shared.db.connection import set_database_path; from infrastructure.db.agent.operator_commands import get_receipt; import sys; set_database_path(sys.argv[1]); print(get_receipt(proposal_id=sys.argv[2], tenant_id=sys.argv[3], workflow_id=sys.argv[4])['receipt_digest'])"
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            program,
            str(connection.DEFAULT_DB_PATH),
            proposal["proposal_id"],
            TENANT,
            run["id"],
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    assert result.stdout.strip() == receipt["receipt_digest"]


def test_expired_proposal_cannot_create_action_but_expired_committed_receipt_replays(
    retry_api, tmp_path, monkeypatch
):
    from datetime import datetime, timedelta, timezone

    client, deps, run, action, _ = source(retry_api, tmp_path)

    class OldDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime.now(timezone.utc) - timedelta(seconds=600)

    with monkeypatch.context() as context:
        context.setattr("domain.workflow.operator_commands.datetime", OldDateTime)
        expired = propose(client, run, action)
    assert confirm(client, run, expired).status_code == 409
    assert_no_retry(deps, run, action)
    proposal = propose(client, run, action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    monkeypatch.setattr(
        "infrastructure.db.agent.operator_retries.proposal_is_expired", lambda _: True
    )
    assert (
        confirm(client, run, proposal).json()["receipt"]["receipt_digest"]
        == receipt["receipt_digest"]
    )


def test_only_durable_pending_retry_holds_its_exact_failure(retry_api, tmp_path):
    from application.services.agent_runtime.runtime.status import (
        compute_next_run_status,
    )
    from application.services.agent_runtime.commands.recovery import create_retry_action

    client, deps, run, action, _ = source(retry_api, tmp_path)
    # A matching-looking dedupe key from the legacy writer grants no v5 hold.
    legacy = create_retry_action(
        deps=deps,
        run_id=run["id"],
        run=run,
        action=action,
        metadata={"retry_strategy": "same_action"},
    )
    assert compute_next_run_status(deps=deps, run=run, run_id=run["id"]) == "failed"
    proposal = propose(client, run, action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    assert receipt["retry_count"] == 2
    assert deps.operator_commands.active_retry_source_ids(
        tenant_id=TENANT, workflow_id=run["id"]
    ) == {action["id"]}
    assert compute_next_run_status(deps=deps, run=run, run_id=run["id"]) == "planned"
    deps.agent_actions.update_agent_action_status(
        action_id=receipt["action_id"], status="rejected"
    )
    assert compute_next_run_status(deps=deps, run=run, run_id=run["id"]) == "failed"
    assert (
        deps.agent_actions.get_agent_action(action_id=legacy["id"])["status"]
        == "proposed"
    )


def test_unrelated_failure_is_not_hidden_by_retry(retry_api, tmp_path):
    from tests.modules.test_approval_effect_authorization import _additional_action
    from application.services.agent_runtime.runtime.status import (
        compute_next_run_status,
    )

    client, deps, run, action, spec = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    assert confirm(client, run, proposal).status_code == 200
    other = _additional_action(deps, run, spec, sequence=3)
    deps.agent_actions.update_agent_action_status(
        action_id=other["id"], status="failed"
    )
    assert compute_next_run_status(deps=deps, run=run, run_id=run["id"]) == "failed"
    assert (
        _post(client, run["id"], message=f"Retry action {action['id']}").json()[
            "command_proposal"
        ]
        is None
    )


def test_exhausted_budget_cannot_be_reset_by_retry(retry_api, tmp_path):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    get_connection().execute(
        "UPDATE agent_runs SET budgets_json = '{\"max_actions\":0}' WHERE id = ?",
        (run["id"],),
    )
    get_connection().commit()
    assert (
        _post(client, run["id"], message=f"Retry action {action['id']}").json()[
            "command_proposal"
        ]
        is None
    )
    assert_no_retry(deps, run, action)


def test_retry_commit_fences_stale_reconciliation_projection(
    retry_api, tmp_path, monkeypatch
):
    from api.runtime_composition import default_runtime

    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    runtime = default_runtime(deps)
    original = deps.agent_runs.transition_agent_run_status
    attempts = []

    class Race:
        def __getattr__(self, name):
            return getattr(deps.agent_runs, name)

        def transition_agent_run_status(self, **kwargs):
            # The retry commits after derivation but before projection write.
            # Its added action must invalidate the stale failure projection.
            attempts.append(confirm(client, run, proposal).status_code)
            return original(**kwargs)

    runtime._deps = dataclasses.replace(deps, agent_runs=Race())
    result = runtime.reconcile_run_status(run_id=run["id"])
    assert result.run["status"] == run["status"]
    assert attempts == [200]
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run["id"])
    assert len(actions) == 2 and actions[-1]["status"] == "proposed"
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action


def test_successful_retry_effect_blocks_repeating_failed_original_source(
    retry_api, tmp_path
):
    from application.services.agent_runtime.registry import get_capability_spec

    client, deps, run, source_action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, source_action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    child = deps.agent_actions.get_agent_action(action_id=receipt["action_id"])
    review = propose_review(client, run, child)
    assert confirm_review(client, run, review).status_code == 200
    child = deps.agent_actions.transition_agent_action_status(
        action_id=child["id"], from_status="approved", to_status="executing"
    )
    spec = get_capability_spec(child["capability_name"])
    authorization = _commit_effect(deps, run, child, spec)
    job = validation_job(deps, child)
    outputs = {"validation_job_id": job["id"]}
    reconcile_authorized_effect(
        deps=deps,
        run=run,
        action=child,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=f"validation-job:{job['id']}",
    )
    deps.agent_actions.update_agent_action_status(
        action_id=child["id"], status="executed", outputs=outputs
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    # Exercise the real gap after effect receipt and lease release, before
    # background run-status reconciliation has projected the original failure.
    response = _post(client, run["id"], message=f"Retry action {source_action['id']}")
    assert response.status_code == 200 and response.json()["command_proposal"] is None
    assert "effect" in response.json()["answer"].lower()
    assert len(deps.agent_actions.list_agent_actions(agent_run_id=run["id"])) == 2
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=run["id"], action_id=child["id"]
    )
    assert effect["status"] == "succeeded"
    assert effect["execution_id"] == authorization.execution_id
