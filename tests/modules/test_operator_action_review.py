"""Exact conversational action decisions compose with durable approval authority."""

import base64
import hashlib
import hmac
import json
import time

import pytest

from infrastructure.db.core.connection import get_connection
from application.services.agent_runtime.registry import get_capability_spec
from tests.modules.test_operator_conversation_cancel import (
    cancel_api as _cancel_fixture,
)
from tests.modules.test_approval_effect_authorization import _run_and_action
from test_operator_conversation_api import TENANT, USER, _post


@pytest.fixture
def review_api(tmp_path, monkeypatch):
    yield from _cancel_fixture.__wrapped__(tmp_path, monkeypatch)


def review_run(review_api, tmp_path):
    client, deps = review_api
    _, run, action, spec = _run_and_action(tmp_path)
    deps.clients.create_client(client_id=TENANT, name="Operator tenant")
    deps.users.ensure_user(USER)
    get_connection().execute(
        "UPDATE agent_runs SET client_id = ? WHERE id = ?", (TENANT, run["id"])
    )
    get_connection().commit()
    run = deps.agent_runs.get_agent_run(run_id=run["id"])
    deps.clients.add_client_user(client_id=TENANT, user_id=USER, role="operator")
    return client, deps, run, action, spec


def headers(run, proposal, **overrides):
    now = int(time.time())
    payload = {
        "schema_version": 2,
        "aud": "operator-action-review-api",
        "iss": "operator-action-review-web-bff",
        "sub": USER,
        "client_id": TENANT,
        "run_id": run["id"],
        "proposal_id": proposal["proposal_id"],
        "proposal_digest": proposal["proposal_digest"],
        "command_type": proposal["command_type"],
        "action_id": proposal["parameters"]["action_id"],
        "iat": now,
        "exp": now + 30,
        "jti": "review-test",
    }
    payload.update(overrides)
    encoded = (
        base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    signature = hmac.new(
        b"operator-command-bff-test-secret-at-least-32",
        encoded.encode(),
        hashlib.sha256,
    ).hexdigest()
    return {"X-Operator-Command-Assertion": f"{encoded}.{signature}"}


def confirm(client, run, proposal, **overrides):
    return client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=headers(run, proposal, **overrides),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": proposal["command_type"],
            "action_id": proposal["parameters"]["action_id"],
        },
    )


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_exact_decision_commits_and_replays(review_api, tmp_path, decision):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    before = deps.agent_actions.get_agent_action(action_id=action["id"])
    response = _post(client, run["id"], message=f"{decision} action {action['id']}")
    assert response.status_code == 200, response.text
    proposal = response.json()["command_proposal"]
    assert proposal is not None, response.json()
    assert proposal["contract"] == "workflow.operator-command-proposal.v4"
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == before
    assert (
        get_connection().execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0]
        == 0
    )
    result = confirm(client, run, proposal)
    assert result.status_code == 200, result.text
    receipt = result.json()["receipt"]
    assert receipt["outcome"] == ("approved" if decision == "approve" else "rejected")
    assert result.json()["run"]["status"] == run["status"]
    current = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert current["approval_id"] == receipt["approval_id"]
    assert current["approval_envelope_digest"] == receipt["approval_envelope_digest"]
    assert current["status"] == receipt["outcome"]
    replay = confirm(client, run, proposal)
    assert replay.status_code == 200, replay.text
    assert replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    assert (
        get_connection().execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0]
        == 1
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM approval_effect_executions")
        .fetchone()[0]
        == 0
    )


def propose(client, run, action, decision="approve"):
    response = _post(client, run["id"], message=f"{decision} action {action['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["command_proposal"] is not None, response.json()
    return response.json()["command_proposal"]


def assert_no_decision(deps, run, action):
    conn = get_connection()
    assert (
        deps.agent_actions.get_agent_action(action_id=action["id"])["status"]
        == "proposed"
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM operator_action_review_receipts").fetchone()[
            0
        ]
        == 0
    )
    assert conn.execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0] == 0
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE event_type IN ('operator_command_approve', 'operator_command_reject')"
        ).fetchone()[0]
        == 0
    )


@pytest.mark.parametrize("decision", ["approve", "reject"])
@pytest.mark.parametrize("status", ["planned", "running", "paused"])
@pytest.mark.parametrize("mode", ["plan_only", "auto_execute_safe"])
def test_source_matrix_preserves_mode_run_state_and_budgets(
    review_api, tmp_path, decision, status, mode
):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    run = deps.agent_runs.update_agent_run(
        run_id=run["id"], status=status, run_mode=mode
    )
    proposal = propose(client, run, action, decision)
    result = confirm(client, run, proposal)
    assert result.status_code == 200, result.text
    current = result.json()["run"]
    for field in (
        "status",
        "run_mode",
        "state",
        "budgets",
        "approval_policy",
        "active_graph_revision",
    ):
        assert current[field] == run[field]


@pytest.mark.parametrize(
    "status",
    [
        "created",
        "planning",
        "failed",
        "completed",
        "canceled",
        "cancelled",
        "PLANNED",
        "unknown",
    ],
)
def test_terminal_and_unsupported_sources_cannot_be_reviewed(
    review_api, tmp_path, status
):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    deps.agent_runs.update_agent_run(run_id=run["id"], status=status)
    assert (
        _post(client, run["id"], message="Approve this action").json()[
            "command_proposal"
        ]
        is None
    )
    assert_no_decision(deps, run, action)


@pytest.mark.parametrize(
    "change",
    [
        "inputs",
        "rationale",
        "budget",
        "mode",
        "revision",
        "policy",
        "lock",
        "membership",
    ],
)
def test_stale_private_state_cannot_commit(review_api, tmp_path, change):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    conn = get_connection()
    if change == "inputs":
        conn.execute(
            "UPDATE agent_actions SET inputs_json = json(?) WHERE id = ?",
            ('{"experiment_id":"changed"}', action["id"]),
        )
    elif change == "rationale":
        conn.execute(
            "UPDATE agent_actions SET rationale_text = 'changed evidence' WHERE id = ?",
            (action["id"],),
        )
    elif change == "budget":
        conn.execute(
            "UPDATE agent_runs SET budgets_json = '{}' WHERE id = ?", (run["id"],)
        )
    elif change == "mode":
        conn.execute(
            "UPDATE agent_runs SET run_mode = 'plan_only' WHERE id = ?", (run["id"],)
        )
    elif change == "revision":
        conn.execute(
            "UPDATE agent_runs SET active_graph_revision = 2 WHERE id = ?", (run["id"],)
        )
    elif change == "policy":
        conn.execute(
            "UPDATE agent_runs SET policy_profile_id = 'changed-policy' WHERE id = ?",
            (run["id"],),
        )
    elif change == "lock":
        assert deps.agent_runs.acquire_run_lock(
            run_id=run["id"], lock_token="competing-worker"
        )
    else:
        conn.execute(
            "UPDATE client_users SET role = 'analyst' WHERE client_id = ? AND user_id = ?",
            (TENANT, USER),
        )
    conn.commit()
    result = confirm(client, run, proposal)
    assert result.status_code in (403, 409), result.text
    assert_no_decision(deps, run, action)


@pytest.mark.parametrize(
    "field,value",
    [
        ("aud", "operator-command-api"),
        ("schema_version", 1),
        ("iss", "operator-command-web-bff"),
        ("action_id", "different-action"),
        ("run_id", "different-run"),
        ("client_id", "different-tenant"),
        ("sub", "different-human"),
        ("command_type", "reject"),
        ("proposal_digest", "0" * 64),
    ],
)
def test_assertion_cannot_substitute_review_authority(
    review_api, tmp_path, field, value
):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    result = confirm(client, run, proposal, **{field: value})
    assert result.status_code in (401, 403), result.text
    assert_no_decision(deps, run, action)


def test_ambiguous_and_batch_targets_never_create_proposals(review_api, tmp_path):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    from tests.modules.test_approval_effect_authorization import _additional_action

    second = _additional_action(
        deps,
        run,
        get_capability_spec(action["capability_name"]),
        dedupe_key="second-action",
    )
    for question in (
        "Approve this action",
        "Approve everything",
        "Approve all actions",
        "Approve action unknown",
        f"Approve action {action['id']} and {second['id']}",
        "Approve and execute this action",
    ):
        response = _post(client, run["id"], message=question)
        assert response.json()["command_proposal"] is None, response.json()
    proposal = propose(client, run, second)
    assert proposal["parameters"]["action_id"] == second["id"]
    assert_no_decision(deps, run, action)


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_fault_after_approval_commit_rolls_back_both_ledgers(
    review_api, tmp_path, decision
):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action, decision)
    conn = get_connection()
    conn.execute(
        "CREATE TRIGGER fail_review_receipt BEFORE INSERT ON operator_action_review_receipts BEGIN SELECT RAISE(ABORT, 'injected receipt failure'); END"
    )
    conn.commit()
    import sqlite3

    with pytest.raises(sqlite3.IntegrityError, match="injected receipt failure"):
        confirm(client, run, proposal)
    assert_no_decision(deps, run, action)
    assert conn.execute("SELECT COUNT(*) FROM approval_records").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM approval_events").fetchone()[0] == 0


def test_competing_approve_reject_and_duplicate_confirmation(review_api, tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    approve, reject = (
        propose(client, run, action),
        propose(client, run, action, "reject"),
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda p: confirm(client, run, p), [approve, reject]))
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = approve if results[0].status_code == 200 else reject
    with ThreadPoolExecutor(max_workers=2) as pool:
        replays = list(pool.map(lambda _: confirm(client, run, winner), range(2)))
    assert all(
        r.status_code == 200 and r.json()["receipt"]["replayed"] for r in replays
    )
    assert (
        get_connection().execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0]
        == 1
    )


def test_cancel_wins_over_pending_decision_and_receipt_replay_survives_cancel(
    review_api, tmp_path
):
    from tests.modules.test_operator_conversation_cancel import (
        propose_cancel,
        confirm_cancel,
    )

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    cancellation = propose_cancel(client, run)
    assert confirm_cancel(client, run, cancellation).status_code == 200
    assert confirm(client, run, proposal).status_code == 409
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "canceled"
    assert (
        get_connection().execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0]
        == 0
    )


def test_existing_requested_approval_must_match_reviewed_action(review_api, tmp_path):
    from application.services.agent_runtime.approval_ledger import (
        issue_action_approval_command,
    )
    from domain.workflow.approval import ApprovalAuthority, PrincipalType

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    authority = ApprovalAuthority(
        principal_type=PrincipalType.HUMAN,
        principal_id="human:" + USER,
        authority_source="agent-principal-token",
        authority_version="agent-principal-signing-secret:v1",
    )
    requested = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="request",
        approving_authority=authority,
        idempotency_key="existing-request",
    )
    proposal = propose(client, run, action)
    assert (
        proposal["parameters"]["review"]["approval_id"]
        == requested["approval"]["approval_id"]
    )
    conn = get_connection()
    conn.execute(
        "UPDATE agent_actions SET inputs_json = json(?), inputs_hash = NULL WHERE id = ?",
        ('{"experiment_id":"new-target"}', action["id"]),
    )
    conn.commit()
    response = _post(client, run["id"], message="Approve this action")
    assert response.json()["command_proposal"] is None, response.json()
    assert confirm(client, run, proposal).status_code == 409
    assert (
        deps.agent_actions.get_agent_action(action_id=action["id"])["status"]
        == "proposed"
    )
    assert conn.execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0] == 1


def test_existing_requested_approval_can_be_confirmed_without_duplicate_request(
    review_api, tmp_path
):
    from application.services.agent_runtime.approval_ledger import (
        issue_action_approval_command,
    )
    from domain.workflow.approval import ApprovalAuthority, PrincipalType

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    authority = ApprovalAuthority(
        principal_type=PrincipalType.HUMAN,
        principal_id="human:" + USER,
        authority_source="agent-principal-token",
        authority_version="agent-principal-signing-secret:v1",
    )
    request = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="request",
        approving_authority=authority,
        idempotency_key="existing-request",
    )
    proposal = propose(client, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    assert (
        response.json()["receipt"]["approval_id"] == request["approval"]["approval_id"]
    )
    assert response.json()["receipt"]["approval_sequence"] == 2
    assert (
        get_connection().execute("SELECT COUNT(*) FROM approval_records").fetchone()[0]
        == 1
    )


def test_replay_after_cancellation_requires_live_membership_and_principal(
    review_api, tmp_path
):
    from tests.modules.test_operator_conversation_cancel import (
        propose_cancel,
        confirm_cancel,
    )

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    cancellation = propose_cancel(client, run)
    assert confirm_cancel(client, run, cancellation).status_code == 200
    replay = confirm(client, run, proposal)
    assert replay.status_code == 200
    assert (
        replay.json()["receipt"]["receipt_digest"]
        == response.json()["receipt"]["receipt_digest"]
    )
    conn = get_connection()
    conn.execute(
        "UPDATE principals SET status = 'inactive' WHERE id = ?", ("human:" + USER,)
    )
    conn.commit()
    assert confirm(client, run, proposal).status_code == 401
    assert conn.execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0] == 1


@pytest.mark.parametrize(
    "table", ["approval_events", "agent_events", "operator_action_review_receipts"]
)
def test_atomic_write_faults_leave_no_decision(review_api, tmp_path, table):
    import sqlite3

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    conn = get_connection()
    conn.execute(
        f"CREATE TRIGGER fail_decision_write BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'decision write fault'); END"
    )
    conn.commit()
    if table == "operator_action_review_receipts":
        with pytest.raises(sqlite3.IntegrityError, match="decision write fault"):
            confirm(client, run, proposal)
    else:
        result = confirm(client, run, proposal)
        assert result.status_code == 409, result.text
    assert_no_decision(deps, run, action)
    assert conn.execute("SELECT COUNT(*) FROM approval_records").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM approval_events").fetchone()[0] == 0


def test_actual_workflow_projection_fault_rolls_back_approval_and_receipt(
    review_api, tmp_path
):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    deps.agent_runs.update_agent_run(
        run_id=run["id"], policy_profile_id="human_approval_required"
    )
    conn = get_connection()
    conn.execute(
        "UPDATE agent_runs SET harness_id = 'operator_supervised', trace_id = 'review-trace' WHERE id = ?",
        (run["id"],),
    )
    conn.commit()
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT, run_id=run["id"]
    )
    proposal = propose(client, run, action)
    conn.execute(
        "CREATE TRIGGER fail_workflow_review_projection BEFORE INSERT ON workflow_compatibility_events BEGIN SELECT RAISE(ABORT, 'workflow projection fault'); END"
    )
    conn.commit()
    result = confirm(client, run, proposal)
    assert result.status_code == 409, result.text
    assert_no_decision(deps, run, action)
    assert conn.execute("SELECT COUNT(*) FROM approval_records").fetchone()[0] == 0
    assert (
        conn.execute("SELECT COUNT(*) FROM workflow_compatibility_events").fetchone()[0]
        == 0
    )


def test_browser_approval_is_consumed_once_at_real_worker_pre_effect_boundary(
    review_api, tmp_path, monkeypatch
):
    from application.services.agent_runtime.worker import AgentRuntimeWorkerService

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    receipt = response.json()["receipt"]
    calls = []

    def execute_capability(**kwargs):
        execution = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=TENANT, workflow_id=run["id"], action_id=action["id"]
        )
        assert execution is not None and execution["status"] == "started"
        assert execution["approval_id"] == receipt["approval_id"]
        assert (
            execution["approval_envelope_digest"] == receipt["approval_envelope_digest"]
        )
        calls.append(execution["execution_id"])
        inputs = deps.agent_actions.get_agent_action(action_id=action["id"])["inputs"]
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
            approval_id=execution["approval_id"],
            effect_idempotency_key=execution["effect_idempotency_key"],
            approval_effect_execution_id=execution["execution_id"],
            input_payload={"source": "worker-test"},
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
    worker = AgentRuntimeWorkerService(deps=deps)
    result = worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=1)
    assert result["steps_executed_total"] == 1, result
    assert len(calls) == 1
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=run["id"], action_id=action["id"]
    )
    assert execution["status"] == "succeeded"
    assert (
        deps.agent_actions.get_agent_action(action_id=action["id"])["status"]
        == "executed"
    )
    worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=1)
    assert len(calls) == 1
    replay = confirm(client, run, proposal)
    assert (
        replay.status_code == 200
        and replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    )


def test_revoked_chat_approval_cannot_cross_worker_boundary(
    review_api, tmp_path, monkeypatch
):
    from application.services.agent_runtime.approval_ledger import (
        issue_action_approval_command,
    )
    from application.services.agent_runtime.worker import AgentRuntimeWorkerService
    from domain.workflow.approval import ApprovalAuthority, PrincipalType

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200
    action = deps.agent_actions.get_agent_action(action_id=action["id"])
    issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="revoke",
        idempotency_key="revoke-chat-approval",
        approving_authority=ApprovalAuthority(
            principal_type=PrincipalType.HUMAN,
            principal_id="human:" + USER,
            authority_source="agent-principal-token",
            authority_version="agent-principal-signing-secret:v1",
        ),
        revocation_reference="review-revoked",
    )
    calls = []
    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **kwargs: calls.append(kwargs),
    )
    AgentRuntimeWorkerService(deps=deps).tick_client(
        client_id=TENANT, user_id=USER, max_steps_per_run=1
    )
    assert calls == []
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM approval_effect_executions")
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "table",
    [
        "operator_action_review_proposals",
        "operator_action_review_receipts",
        "agent_events",
    ],
)
@pytest.mark.parametrize("operation", ["update", "delete", "replace"])
def test_review_and_linked_audits_are_immutable(review_api, tmp_path, table, operation):
    import sqlite3

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    result = confirm(client, run, proposal)
    assert result.status_code == 200
    receipt = result.json()["receipt"]
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
                ("replaced-identity", identity),
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


def test_migration_060_preserves_old_bytes_views_cursors_and_replay(
    review_api, tmp_path
):
    from shared.db.migrations import apply_migrations
    from tests.modules.test_operator_conversation_cancel import (
        eligible_run,
        propose_cancel,
        confirm_cancel,
    )
    from tests.modules.test_operator_conversation_resume import (
        confirm as confirm_control,
        propose as propose_resume,
    )

    client, deps, run, action, _ = review_run(review_api, tmp_path)
    legacy_run = eligible_run(deps)
    resume = propose_resume(client, legacy_run)
    assert confirm_control(client, legacy_run, resume).status_code == 200
    pause = _post(client, legacy_run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert (
        confirm_control(client, legacy_run, pause, command_type="pause").status_code
        == 200
    )
    cancel = propose_cancel(client, legacy_run)
    assert confirm_cancel(client, legacy_run, cancel).status_code == 200
    conn = get_connection()
    tables = (
        "operator_command_proposals",
        "operator_command_receipts",
        "operator_resume_proposals",
        "operator_resume_receipts",
        "operator_cancel_proposals",
        "operator_cancel_receipts",
    )
    before = {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
        for table in tables
    }
    cursor = deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=legacy_run["id"], limit=1
    )["page"]["next_cursor"]
    for view in ("operator_all_proposals_v4", "operator_all_receipts_v4"):
        conn.execute(f"DROP VIEW {view}")
    for suffix in ("no_update", "no_delete", "no_replace"):
        conn.execute(f"DROP TRIGGER operator_action_review_audit_{suffix}")
    for table in (
        "operator_action_review_receipts",
        "operator_action_review_proposals",
    ):
        conn.execute(f"DROP TABLE {table}")
    conn.execute(
        "DELETE FROM schema_migrations WHERE name = '060_operator_conversation_action_reviews.sql'"
    )
    conn.commit()
    apply_migrations(conn)
    assert {
        table: [tuple(row) for row in conn.execute(f"SELECT * FROM {table}")]
        for table in tables
    } == before
    assert deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=legacy_run["id"], limit=1, cursor=cursor
    )["records"]
    for decision, proposal in (
        ("resume", resume),
        ("pause", pause),
        ("cancel", cancel),
    ):
        assert (
            confirm_control(client, legacy_run, proposal, command_type=decision).json()[
                "receipt"
            ]["replayed"]
            is True
        )
    proposal = propose(client, run, action)
    assert confirm(client, run, proposal).status_code == 200
    assert conn.execute("SELECT COUNT(*) FROM operator_all_receipts").fetchone()[0] == 2
    assert (
        conn.execute("SELECT COUNT(*) FROM operator_all_receipts_v3").fetchone()[0] == 3
    )
    assert (
        conn.execute("SELECT COUNT(*) FROM operator_all_receipts_v4").fetchone()[0] == 4
    )
    assert {
        record["proposal"]["command_type"]
        for record in deps.operator_commands.list_records(
            tenant_id=TENANT, workflow_id=run["id"]
        )["records"]
    } == {"approve"}


def test_joined_approval_failure_preserves_callers_unrelated_work(review_api, tmp_path):
    from infrastructure.db.core.transactions import JoinedTransaction

    _, _, _, _, _ = review_run(review_api, tmp_path)
    conn = get_connection()
    conn.execute("BEGIN IMMEDIATE")
    conn.execute("INSERT INTO users(id) VALUES ('outer-unrelated-user')")
    inner = JoinedTransaction(conn, "approval_command_test")
    conn.execute("INSERT INTO users(id) VALUES ('inner-rollback-user')")
    inner.rollback()
    assert conn.in_transaction
    assert conn.execute(
        "SELECT id FROM users WHERE id = 'outer-unrelated-user'"
    ).fetchone()
    assert (
        conn.execute("SELECT id FROM users WHERE id = 'inner-rollback-user'").fetchone()
        is None
    )
    conn.rollback()
