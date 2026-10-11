"""Independent effect/approval/audit oracles for conversational reconciliation."""

import pytest

from infrastructure.db.core.connection import get_connection
from application.services.agent_runtime.approval_authorization import (
    mark_authorized_effect_uncertain,
)
from tests.modules.test_operator_action_review import (
    review_api as _fixture,
    review_run,
    headers,
)
from tests.modules.test_approval_effect_authorization import _approve, _commit_effect
from tests.modules.test_operator_retry_integrity import validation_job
from test_operator_conversation_api import TENANT, USER, _post


@pytest.fixture
def reconciliation_api(tmp_path, monkeypatch):
    yield from _fixture.__wrapped__(tmp_path, monkeypatch)


def source(reconciliation_api, tmp_path, *, status="failed", auto_run=True):
    client, deps, run, action, spec = review_run(reconciliation_api, tmp_path)
    if not auto_run:
        import json

        conn = get_connection()
        conn.execute(
            "UPDATE agent_actions SET inputs_json = json(?) WHERE id = ?",
            (json.dumps({**action["inputs"], "auto_run": False}), action["id"]),
        )
        conn.commit()
        action = deps.agent_actions.get_agent_action(action_id=action["id"])
    _approve(deps, run, action)
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    auth = _commit_effect(deps, run, action, spec)
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=action,
        authorization=auth,
        error_code="lost_acknowledgement",
    )
    job = validation_job(deps, action)
    action = deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="lost outcome"
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    run = deps.agent_runs.update_agent_run(run_id=run["id"], status=status)
    return client, deps, run, action, job


def propose(client, run, action):
    response = _post(client, run["id"], message=f"Reconcile action {action['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["command_proposal"], response.json()
    return response.json()["command_proposal"]


def confirm(client, run, proposal, **overrides):
    effect_id = proposal["parameters"]["effect_execution_id"]
    return client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=headers(
            run,
            proposal,
            **{
                "schema_version": 4,
                "aud": "operator-reconciliation-api",
                "iss": "operator-reconciliation-web-bff",
                "effect_execution_id": effect_id,
                **overrides,
            },
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": "reconcile_effect",
            "action_id": proposal["parameters"]["action_id"],
            "effect_execution_id": effect_id,
        },
    )


@pytest.mark.parametrize(
    "status", ["planned", "running", "failed", "paused", "completed", "canceled"]
)
def test_existing_outcome_is_recorded_without_execution_and_terminal_revival(
    reconciliation_api, tmp_path, monkeypatch, status
):
    client, deps, run, action, job = source(reconciliation_api, tmp_path, status=status)

    def forbidden(**_):
        pytest.fail("Reconciliation invoked a capability")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", forbidden
    )
    conn = get_connection()
    before = {
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in (
            "approval_effect_executions",
            "approval_commands",
            "approval_events",
            "agent_actions",
            "validation_jobs",
            "validation_results",
        )
    }
    proposal = propose(client, run, action)
    assert proposal["contract"] == "workflow.operator-command-proposal.v6"
    assert proposal["parameters"]["reconciliation"]["verification_state"] == "verified"
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action
    assert {
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in before
    } == before
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    receipt = response.json()["receipt"]
    assert receipt["outcome"] == "succeeded" and receipt["action_status"] == "executed"
    expected = status if status in {"paused", "completed", "canceled"} else "planned"
    assert response.json()["run"]["status"] == expected
    assert receipt["resulting_run_status"] == expected
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=run["id"], action_id=action["id"]
    )
    assert (
        effect["status"] == "succeeded"
        and effect["receipt_id"] == f"validation-job:{job['id']}"
    )
    updated = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert updated["status"] == "executed" and updated["validation_job_id"] == job["id"]
    approval = deps.approval_ledger.get_approval(
        tenant_id=TENANT, workflow_id=run["id"], approval_id=effect["approval_id"]
    )
    assert approval["status"] == "fulfilled"
    assert (
        conn.execute("SELECT count(*) FROM approval_effect_executions").fetchone()[0]
        == before["approval_effect_executions"]
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM approval_commands WHERE command_type = 'fulfill'"
        ).fetchone()[0]
        == 1
    )
    for _ in range(2):
        replay = confirm(client, run, proposal)
        assert replay.status_code == 200, replay.text
        assert (
            replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
            and replay.json()["receipt"]["replayed"]
        )
    assert (
        conn.execute(
            "SELECT count(*) FROM operator_reconciliation_receipts"
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM agent_events WHERE event_type = 'operator_command_reconcile_effect'"
        ).fetchone()[0]
        == 1
    )
    assert not conn.in_transaction


def assert_unrecorded(deps, run, action):
    conn = get_connection()
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=run["id"], action_id=action["id"]
    )
    assert effect["status"] == "uncertain" and effect["receipt_id"] is None
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == run["status"]
    assert (
        deps.approval_ledger.get_approval(
            tenant_id=TENANT, workflow_id=run["id"], approval_id=effect["approval_id"]
        )["status"]
        == "approved"
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM approval_commands WHERE command_type = 'fulfill'"
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM operator_reconciliation_receipts"
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT count(*) FROM agent_events WHERE event_type IN ('operator_command_reconcile_effect','action_effect_reconciled','approval_effect_succeeded','approval_fulfilled','action_executed')"
        ).fetchone()[0]
        == 0
    )
    assert not conn.in_transaction


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 1),
        ("schema_version", 2),
        ("schema_version", 3),
        ("aud", "operator-retry-api"),
        ("iss", "operator-action-review-web-bff"),
        ("sub", "other-human"),
        ("client_id", "other-tenant"),
        ("run_id", "other-run"),
        ("action_id", "other-action"),
        ("effect_execution_id", "other-effect"),
        ("proposal_id", "other-proposal"),
        ("proposal_digest", "0" * 64),
        ("command_type", "retry"),
    ],
)
def test_exact_reconciliation_assertion_is_separate_authority(
    reconciliation_api, tmp_path, field, value
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    assert confirm(client, run, proposal, **{field: value}).status_code in {401, 403}
    assert_unrecorded(deps, run, action)


@pytest.mark.parametrize(
    "message",
    [
        "Reconcile actions",
        "Reconcile action 1 then step the run",
        "Reconcile action 1 then stop the run",
        "Reconcile action 1 and action 2",
        "Reconcile action 1 and 2",
        "Reconcile action missing",
        "Reconcile all",
        "Reconcile and retry action 1",
        "Reconcile action 1 and cancel this run",
    ],
)
def test_multiple_unresolved_or_combined_targets_create_no_proposal(
    reconciliation_api, tmp_path, message
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    response = _post(client, run["id"], message=message)
    assert response.status_code == 200 and response.json()["command_proposal"] is None
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_reconciliation_proposals")
        .fetchone()[0]
        == 0
    )
    assert_unrecorded(deps, run, action)


@pytest.mark.parametrize(
    "change",
    [
        "job_status",
        "job_scope",
        "job_identity",
        "result",
        "result_payload",
        "revision",
        "action",
        "lease",
        "role",
        "cancel",
    ],
)
def test_final_lock_rechecks_evidence_and_control(
    reconciliation_api, tmp_path, monkeypatch, change
):
    import dataclasses
    from api.main import app
    from api.routes import operator_conversation

    client, deps, run, action, job = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    store = deps.operator_commands

    class Race:
        def __getattr__(self, name):
            return getattr(store, name)

        def commit_reconciliation(self, **kwargs):
            conn = get_connection()
            mutations = {
                "job_status": (
                    "UPDATE validation_jobs SET status = 'running' WHERE id = ?",
                    job["id"],
                ),
                "job_scope": (
                    "UPDATE validation_jobs SET entity_id = 'other-experiment' WHERE id = ?",
                    job["id"],
                ),
                "job_identity": (
                    "UPDATE validation_jobs SET provider = 'other-provider' WHERE id = ?",
                    job["id"],
                ),
                "result": (
                    "UPDATE validation_results SET provider = 'other-provider' WHERE job_id = ?",
                    job["id"],
                ),
                "result_payload": (
                    'UPDATE validation_results SET structured_result_json = \'{"observed":"new-value"}\' WHERE job_id = ?',
                    job["id"],
                ),
                "revision": (
                    "UPDATE agent_runs SET active_graph_revision = 2 WHERE id = ?",
                    run["id"],
                ),
                "action": (
                    "UPDATE agent_actions SET inputs_json = '{}' WHERE id = ?",
                    action["id"],
                ),
                "lease": (
                    "UPDATE agent_runs SET lock_token = 'live-worker' WHERE id = ?",
                    run["id"],
                ),
                "role": (
                    "UPDATE client_users SET role = 'analyst' WHERE user_id = ?",
                    USER,
                ),
                "cancel": (
                    "UPDATE agent_runs SET status = 'canceled' WHERE id = ?",
                    run["id"],
                ),
            }
            sql, key = mutations[change]
            conn.execute(sql, (key,))
            conn.commit()
            return store.commit_reconciliation(**kwargs)

    app.dependency_overrides[operator_conversation._deps] = lambda: dataclasses.replace(
        deps, operator_commands=Race()
    )
    assert confirm(client, run, proposal).status_code in {403, 409}
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_reconciliation_receipts")
        .fetchone()[0]
        == 0
    )
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=run["id"], action_id=action["id"]
    )
    assert effect["status"] == "uncertain"


@pytest.mark.parametrize(
    "table,operation",
    [
        ("approval_commands", "INSERT"),
        ("approval_events", "INSERT"),
        ("approval_effect_executions", "UPDATE"),
        ("agent_actions", "UPDATE"),
        ("agent_events", "INSERT"),
        ("agent_runs", "UPDATE"),
        ("operator_reconciliation_receipts", "INSERT"),
    ],
)
def test_required_write_faults_roll_back_every_new_record(
    reconciliation_api, tmp_path, table, operation
):
    import sqlite3

    client, deps, run, action, job = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    conn = get_connection()
    conn.execute(
        f"CREATE TRIGGER reconciliation_fault BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT, 'original reconciliation write fault'); END"
    )
    conn.commit()
    with pytest.raises(
        sqlite3.IntegrityError, match="original reconciliation write fault"
    ):
        confirm(client, run, proposal)
    deps.users.ensure_user("unrelated-later-writer")
    assert_unrecorded(deps, run, action)
    assert (
        deps.validation_jobs.get_job(job_id=job["id"], client_id=TENANT)["status"]
        == "completed"
    )


def test_final_commit_failure_preserves_exception_and_clears_pending_writes(
    reconciliation_api, tmp_path, monkeypatch
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)

    class CommitFault:
        def __init__(self):
            self.conn = get_connection()

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def commit(self):
            raise RuntimeError("original final commit failure")

    monkeypatch.setattr(
        "infrastructure.db.agent.operator_reconciliations.get_connection",
        lambda: CommitFault(),
    )
    with pytest.raises(RuntimeError, match="original final commit failure"):
        confirm(client, run, proposal)
    deps.users.ensure_user("unrelated-after-commit-failure")
    assert_unrecorded(deps, run, action)


def test_competing_confirmations_and_background_winner_are_coherent(
    reconciliation_api, tmp_path
):
    from concurrent.futures import ThreadPoolExecutor

    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposals = [propose(client, run, action) for _ in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda p: confirm(client, run, p), proposals))
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = proposals[0 if results[0].status_code == 200 else 1]
    with ThreadPoolExecutor(max_workers=2) as pool:
        replays = list(pool.map(lambda _: confirm(client, run, winner), range(2)))
    assert all(
        r.status_code == 200 and r.json()["receipt"]["replayed"] for r in replays
    )
    assert (
        get_connection()
        .execute(
            "SELECT count(*) FROM approval_commands WHERE command_type = 'fulfill'"
        )
        .fetchone()[0]
        == 1
    )
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_reconciliation_receipts")
        .fetchone()[0]
        == 1
    )


def test_background_recovery_wins_then_fresh_review_records_existing_success(
    reconciliation_api, tmp_path
):
    from application.services.agent_runtime.effect_recovery import (
        reconcile_effect_from_durable_evidence,
    )

    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    stale = propose(client, run, action)
    recovered = reconcile_effect_from_durable_evidence(
        deps=deps, run=run, action=action
    )
    assert recovered["effect_execution"]["status"] == "succeeded"
    assert confirm(client, run, stale).status_code == 409
    fresh = propose(client, recovered["run"], recovered["action"])
    assert confirm(client, recovered["run"], fresh).status_code == 200
    assert (
        get_connection()
        .execute(
            "SELECT count(*) FROM approval_commands WHERE command_type = 'fulfill'"
        )
        .fetchone()[0]
        == 1
    )


def test_existing_stopping_marker_is_preserved_across_legacy_start(
    reconciliation_api, tmp_path
):
    client, deps, run, action, _ = source(
        reconciliation_api, tmp_path, status="planned"
    )
    stop = deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=None,
        sequence=0,
        event_type="run_stopping_condition_met",
        status="planned",
        anchors={"stopping_condition": "policy_block"},
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=None,
        sequence=0,
        event_type="run_started",
        status="running",
    )
    receipt = confirm(client, run, propose(client, run, action)).json()["receipt"]
    assert (
        receipt["control_state_preserved"]
        and receipt["resulting_run_status"] == "planned"
    )
    assert (
        get_connection()
        .execute(
            "SELECT count(*) FROM agent_events WHERE event_type = 'run_stopping_condition_cleared'"
        )
        .fetchone()[0]
        == 0
    )
    assert deps.agent_events.get_agent_event(stop["id"])


def test_fresh_process_replay_survives_expiry_and_state_changes(
    reconciliation_api, tmp_path, monkeypatch
):
    import subprocess
    import sys
    from shared.db import connection

    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    deps.agent_runs.update_agent_run(run_id=run["id"], status="canceled")
    monkeypatch.setattr(
        "infrastructure.db.agent.operator_reconciliations.proposal_is_expired",
        lambda _: True,
    )
    assert (
        confirm(client, run, proposal).json()["receipt"]["receipt_digest"]
        == receipt["receipt_digest"]
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
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == receipt["receipt_digest"]
    conn = get_connection()
    conn.execute("UPDATE client_users SET role = 'analyst' WHERE user_id = ?", (USER,))
    conn.commit()
    assert confirm(client, run, proposal).status_code == 403


@pytest.mark.parametrize("auto_run,expected", [(True, False), (False, True)])
def test_frozen_auto_run_controls_required_evidence(
    reconciliation_api, tmp_path, auto_run, expected
):
    client, deps, run, action, job = source(
        reconciliation_api, tmp_path, auto_run=auto_run
    )
    conn = get_connection()
    conn.execute(
        "UPDATE validation_jobs SET status = 'created' WHERE id = ?", (job["id"],)
    )
    conn.execute("DELETE FROM validation_results WHERE job_id = ?", (job["id"],))
    conn.commit()
    response = _post(client, run["id"], message="Reconcile action 1")
    assert response.status_code == 200
    assert bool(response.json()["command_proposal"]) is expected
    if expected:
        assert (
            confirm(client, run, response.json()["command_proposal"]).status_code == 200
        )
    else:
        assert_unrecorded(deps, run, action)


@pytest.mark.parametrize(
    "change", ["missing_snapshot", "bad_digest", "wrong_action", "cross_scope"]
)
def test_unverified_or_substituted_start_cannot_be_proposed(
    reconciliation_api, tmp_path, monkeypatch, change
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    original = deps.approval_ledger.get_effect_execution_for_action

    def substitute(**kwargs):
        effect = original(**kwargs)
        if not effect:
            return effect
        return {
            **effect,
            **{
                "missing_snapshot": {
                    "authorization_snapshot": None,
                    "authorization_snapshot_digest": None,
                },
                "bad_digest": {"authorization_snapshot_digest": "0" * 64},
                "wrong_action": {"action_id": "wrong-action"},
                "cross_scope": {"tenant_id": "wrong-tenant"},
            }[change],
        }

    monkeypatch.setattr(
        deps.approval_ledger, "get_effect_execution_for_action", substitute
    )
    response = _post(client, run["id"], message="Reconcile action 1")
    assert response.status_code == 200 and response.json()["command_proposal"] is None
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_reconciliation_proposals")
        .fetchone()[0]
        == 0
    )


def test_current_registry_policy_drift_does_not_reauthorize_historical_outcome(
    reconciliation_api, tmp_path, monkeypatch
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    conn = get_connection()
    conn.execute(
        "UPDATE agent_runs SET policy_profile_id = 'observe', registry_version = 'new-version', registry_fingerprint = 'new-fingerprint' WHERE id = ?",
        (run["id"],),
    )
    conn.commit()

    def forbidden(**_):
        pytest.fail("Historical recovery consulted current executable authority")

    monkeypatch.setattr(
        "application.services.agent_runtime.approval_authorization.prepare_action_for_exact_approval",
        forbidden,
    )
    proposal = propose(client, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    assert (
        response.json()["receipt"]["reconciliation"]["authorization_snapshot_digest"]
        == proposal["parameters"]["reconciliation"]["authorization_snapshot_digest"]
    )


def test_expired_approval_can_fulfill_a_then_valid_effect_start(
    reconciliation_api, tmp_path
):
    from datetime import datetime, timedelta, timezone
    from application.services.agent_runtime.approval_ledger import (
        issue_action_approval_command,
    )
    from tests.modules.approval_effect_support import approval_authority

    client, deps, run, action, spec = review_run(reconciliation_api, tmp_path)
    decided = datetime.now(timezone.utc) - timedelta(seconds=10)
    issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=approval_authority(),
        idempotency_key="approve-short-lived",
        occurred_at=decided,
        ttl_seconds=1,
    )
    action = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    auth = _commit_effect(
        deps, run, action, spec, now=decided + timedelta(milliseconds=500)
    )
    mark_authorized_effect_uncertain(
        deps=deps, run=run, action=action, authorization=auth, error_code="lost"
    )
    validation_job(deps, action)
    action = deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed"
    )
    deps.agent_runs.release_run_lock(run_id=run["id"], lock_token="worker-a")
    response = confirm(client, run, propose(client, run, action))
    assert response.status_code == 200, response.text
    assert (
        get_connection()
        .execute(
            "SELECT count(*) FROM approval_commands WHERE command_type = 'fulfill'"
        )
        .fetchone()[0]
        == 1
    )


@pytest.mark.parametrize(
    "table",
    [
        "operator_reconciliation_proposals",
        "operator_reconciliation_receipts",
        "agent_events",
    ],
)
@pytest.mark.parametrize("operation", ["update", "delete", "replace"])
def test_proposals_receipts_and_human_audits_are_immutable(
    reconciliation_api, tmp_path, table, operation
):
    import sqlite3

    client, _, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    receipt = confirm(client, run, proposal).json()["receipt"]
    conn = get_connection()
    key = "id" if table == "agent_events" else "proposal_id"
    identity = (
        receipt["event_ids"]["command"]
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


def test_expired_proposal_is_read_only(reconciliation_api, tmp_path, monkeypatch):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    monkeypatch.setattr(
        "infrastructure.db.agent.operator_reconciliations.proposal_is_expired",
        lambda _: True,
    )
    assert confirm(client, run, proposal).status_code == 409
    assert_unrecorded(deps, run, action)


def test_lab_receipt_records_once_without_reexecuting_local_effect(
    reconciliation_api, tmp_path, monkeypatch
):
    from application.services.agent_runtime.runtime import (
        AgentRuntimeService,
        authorized_execution,
    )
    from application.services.agent_runtime.capabilities import CapabilityExecutionError
    from tests.modules.test_governed_effect_receipts import _lab_action
    from test_operator_conversation_api import _headers

    client, deps = reconciliation_api
    _, run, action, _, _, _, _ = _lab_action(tmp_path)
    deps.users.ensure_user(USER)
    deps.clients.add_client_user(client_id="client-a", user_id=USER, role="operator")
    _approve(deps, run, action)
    completion = authorized_execution.complete_authorized_effect

    def lost(**_):
        raise RuntimeError("lost local effect acknowledgement")

    monkeypatch.setattr(authorized_execution, "complete_authorized_effect", lost)
    with pytest.raises(
        CapabilityExecutionError, match="lost local effect acknowledgement"
    ):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id=USER)
    monkeypatch.setattr(authorized_execution, "complete_authorized_effect", completion)

    def forbidden(**_):
        pytest.fail("Reconciliation repeated the local capability")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", forbidden
    )
    conn = get_connection()
    before = {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
        for t in (
            "approval_effect_executions",
            "governed_effect_receipts",
            "analytics_events",
            "decision_events",
        )
    }
    response = client.post(
        f"/conversation/operator/runs/{run['id']}/message",
        headers=_headers(client_id="client-a"),
        json={
            "client_id": "client-a",
            "user_id": USER,
            "message": "Reconcile action 1",
        },
    )
    assert response.status_code == 200, response.text
    proposal = response.json()["command_proposal"]
    assert proposal, response.json()
    effect_id = proposal["parameters"]["effect_execution_id"]
    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=headers(
            run,
            proposal,
            schema_version=4,
            aud="operator-reconciliation-api",
            iss="operator-reconciliation-web-bff",
            client_id="client-a",
            effect_execution_id=effect_id,
        ),
        json={
            "client_id": "client-a",
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": "reconcile_effect",
            "action_id": action["id"],
            "effect_execution_id": effect_id,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["receipt"]["reconciliation"]["receipt_id"].startswith(
        "lab-promotion:"
    )
    assert {
        t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in before
    } == before


def test_migration_062_preserves_v1_to_v5_bytes_readers_and_cursors(
    reconciliation_api, tmp_path
):
    from shared.db.migrations import apply_migrations
    from tests.modules.test_operator_retry_integrity import (
        test_migration_061_preserves_previous_contracts_and_cursor_replay,
    )

    # Establish actual v1-v5 receipts through each authenticated production path.
    test_migration_061_preserves_previous_contracts_and_cursor_replay(
        reconciliation_api, tmp_path
    )
    _, deps = reconciliation_api
    conn = get_connection()
    tables = [
        f"operator_{stem}_{kind}"
        for stem in ("command", "resume", "cancel", "action_review", "retry")
        for kind in ("proposals", "receipts")
    ]
    before = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")] for t in tables}
    run_id = conn.execute(
        "SELECT workflow_id FROM operator_resume_proposals"
    ).fetchone()[0]
    page = deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run_id, limit=1
    )
    cursor = page["page"]["next_cursor"]
    old = conn.execute("SELECT * FROM operator_retry_receipts").fetchone()
    expected = deps.operator_commands.get_receipt(
        proposal_id=old["proposal_id"], tenant_id=TENANT, workflow_id=old["workflow_id"]
    )
    conn.executescript(
        "DROP VIEW operator_all_receipts_v6; DROP VIEW operator_all_proposals_v6; DROP TRIGGER operator_reconciliation_audit_no_update; DROP TRIGGER operator_reconciliation_audit_no_delete; DROP TRIGGER operator_reconciliation_audit_no_replace; DROP TABLE operator_reconciliation_receipts; DROP TABLE operator_reconciliation_proposals; DELETE FROM schema_migrations WHERE name = '062_operator_conversation_reconciliation.sql';"
    )
    apply_migrations(conn)
    assert {
        t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")] for t in tables
    } == before
    assert deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run_id, limit=1, cursor=cursor
    )["records"]
    assert (
        deps.operator_commands.get_receipt(
            proposal_id=old["proposal_id"],
            tenant_id=TENANT,
            workflow_id=old["workflow_id"],
        )
        == expected
    )
    assert (
        conn.execute("SELECT count(*) FROM operator_all_receipts_v5").fetchone()[0] == 5
    )
    assert (
        conn.execute("SELECT count(*) FROM operator_all_receipts_v6").fetchone()[0] == 5
    )
