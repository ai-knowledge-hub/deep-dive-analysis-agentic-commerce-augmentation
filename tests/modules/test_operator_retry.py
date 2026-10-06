"""Independent durable oracles for exact retry creation, authority and rollback."""

import dataclasses
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from api.runtime_composition import default_completion_coordinator
from application.services.conversation.operator_gateway import (
    OperatorConversationService,
)
from infrastructure.db.core.connection import get_connection
from tests.modules.test_operator_action_review import (
    review_api as _fixture,
    review_run,
    headers,
    propose as propose_review,
    confirm as confirm_review,
)
from test_operator_conversation_api import TENANT, USER, _post


@pytest.fixture
def retry_api(tmp_path, monkeypatch):
    yield from _fixture.__wrapped__(tmp_path, monkeypatch)


def source(retry_api, tmp_path):
    client, deps, run, action, spec = review_run(retry_api, tmp_path)
    action = deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="failed before effect"
    )
    return client, deps, run, action, spec


def propose(client, run, action):
    response = _post(client, run["id"], message=f"Retry action {action['id']}")
    assert response.status_code == 200, response.text
    assert response.json()["command_proposal"] is not None, response.json()
    return response.json()["command_proposal"]


def confirm(client, run, proposal, **overrides):
    return client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=headers(
            run,
            proposal,
            **{
                "schema_version": 3,
                "aud": "operator-retry-api",
                "iss": "operator-retry-web-bff",
                "retry_strategy": "same_action",
                **overrides,
            },
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": "retry",
            "action_id": proposal["parameters"]["action_id"],
            "retry_strategy": "same_action",
        },
    )


def assert_no_retry(deps, run, action):
    conn = get_connection()
    assert len(deps.agent_actions.list_agent_actions(agent_run_id=run["id"])) == 1
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action
    assert (
        conn.execute("SELECT COUNT(*) FROM operator_retry_receipts").fetchone()[0] == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE event_type IN ('operator_command_retry', 'action_retry_proposed')"
        ).fetchone()[0]
        == 0
    )
    assert conn.execute("SELECT COUNT(*) FROM approval_commands").fetchone()[0] == 0
    assert not conn.in_transaction


@pytest.mark.parametrize("status", ["planned", "running", "paused"])
@pytest.mark.parametrize("mode", ["plan_only", "auto_execute_safe"])
def test_exact_retry_is_read_only_until_atomic_confirmation(
    retry_api, tmp_path, status, mode
):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    run = deps.agent_runs.update_agent_run(
        run_id=run["id"], status=status, run_mode=mode
    )
    proposal = propose(client, run, action)
    assert proposal["contract"] == "workflow.operator-command-proposal.v5"
    assert proposal["parameters"]["retry_strategy"] == "same_action"
    assert_no_retry(deps, run, action)
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    receipt = response.json()["receipt"]
    child = deps.agent_actions.get_agent_action(action_id=receipt["action_id"])
    assert receipt["contract"] == "workflow.operator-command-receipt.v5"
    assert (
        receipt["outcome"] == "proposed" and receipt["source_action_id"] == action["id"]
    )
    assert receipt["retry_count"] == 1 and receipt["action_sequence"] == 2
    assert child["dedupe_key"] == f"retry:{action['id']}:same_action:1"
    assert child["status"] == "proposed" and child["approval_id"] is None
    assert (
        child["outputs"] == {}
        and child["validation_job_id"] is None
        and child["receipt_id"] is None
    )
    assert child["inputs"] == proposal["parameters"]["retry_plan"]["normalized_inputs"]
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action
    assert response.json()["run"] == run
    conn = get_connection()
    assert (
        conn.execute("SELECT COUNT(*) FROM approval_effect_executions").fetchone()[0]
        == 0
    )
    audits = conn.execute(
        "SELECT * FROM agent_events WHERE event_type IN ('operator_command_retry','action_retry_proposed')"
    ).fetchall()
    assert len(audits) == 2 and all(
        a["principal_id"] == f"human:{USER}" and a["action_id"] == child["id"]
        for a in audits
    )
    replay = confirm(client, run, proposal)
    assert (
        replay.status_code == 200
        and replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    )
    assert replay.json()["receipt"]["replayed"]
    fresh_review = propose_review(client, run, child)
    approval = confirm_review(client, run, fresh_review)
    assert approval.status_code == 200, approval.text
    assert approval.json()["receipt"]["action_id"] == child["id"]
    assert (
        confirm(client, run, proposal).json()["receipt"]["receipt_digest"]
        == receipt["receipt_digest"]
    )


@pytest.mark.parametrize(
    "status",
    ["created", "planning", "failed", "completed", "canceled", "cancelled", "unknown"],
)
def test_terminal_or_unsupported_run_cannot_receive_retry(retry_api, tmp_path, status):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    deps.agent_runs.update_agent_run(run_id=run["id"], status=status)
    result = _post(client, run["id"], message="Retry this action").json()
    assert result["command_proposal"] is None
    assert_no_retry(deps, run, action)


@pytest.mark.parametrize(
    "message",
    [
        "Retry actions",
        "Retry action 1 and action 2",
        "Retry action 1 and 2",
        "Retry action 999",
        "Retry and execute action 1",
        "Retry all",
        "Retry action 1 from checkpoint",
        "Approve and retry action 1",
        "Retry action 1 and cancel this run",
    ],
)
def test_batch_unknown_or_combined_commands_cannot_create_work(
    retry_api, tmp_path, message
):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    result = _post(client, run["id"], message=message)
    assert result.status_code == 200 and result.json()["command_proposal"] is None
    assert_no_retry(deps, run, action)


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", 2),
        ("aud", "operator-action-review-api"),
        ("iss", "operator-command-web-bff"),
        ("action_id", "different-action"),
        ("sub", "other-human"),
        ("client_id", "other-tenant"),
        ("run_id", "other-run"),
        ("retry_strategy", "last_safe_checkpoint"),
        ("command_type", "approve"),
        ("proposal_digest", "0" * 64),
    ],
)
def test_retry_assertion_has_exact_separate_authority(
    retry_api, tmp_path, field, value
):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    result = confirm(client, run, proposal, **{field: value})
    assert result.status_code in (401, 403)
    assert_no_retry(deps, run, action)


@pytest.mark.parametrize(
    "change",
    ["inputs", "revision", "budget", "policy", "mode", "lock", "status", "membership"],
)
def test_stale_fenced_state_blocks_confirmation(retry_api, tmp_path, change):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    conn = get_connection()
    if change == "inputs":
        conn.execute(
            'UPDATE agent_actions SET inputs_json = \'{"experiment_id":"changed"}\' WHERE id = ?',
            (action["id"],),
        )
    elif change == "membership":
        conn.execute(
            "UPDATE client_users SET role = 'analyst' WHERE client_id = ? AND user_id = ?",
            (TENANT, USER),
        )
    else:
        column, value = {
            "revision": ("active_graph_revision", 2),
            "budget": ("budgets_json", "{}"),
            "policy": ("policy_profile_id", "observe"),
            "mode": ("run_mode", "plan_only"),
            "lock": ("lock_token", "worker"),
            "status": ("status", "canceled"),
        }[change]
        conn.execute(
            f"UPDATE agent_runs SET {column} = ? WHERE id = ?", (value, run["id"])
        )
    conn.commit()
    changed = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert confirm(client, run, proposal).status_code in (403, 409)
    assert_no_retry(deps, run, changed)


@pytest.mark.parametrize(
    "table", ["agent_actions", "agent_events", "operator_retry_receipts"]
)
def test_write_faults_fully_roll_back_retry(retry_api, tmp_path, table):
    client, deps, run, action, _ = source(retry_api, tmp_path)
    proposal = propose(client, run, action)
    conn = get_connection()
    conn.execute(
        f"CREATE TRIGGER retry_fault BEFORE INSERT ON {table} BEGIN SELECT RAISE(ABORT, 'retry write fault'); END"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="retry write fault"):
        confirm(client, run, proposal)
    deps.users.ensure_user("unrelated-later-writer")
    assert_no_retry(deps, run, action)


def test_competing_and_duplicate_confirmations_allocate_once(retry_api, tmp_path):
    client, deps, run, action, _ = source(retry_api, tmp_path)
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
    later = propose(client, run, action)
    result = confirm(client, run, later)
    assert result.status_code == 200 and result.json()["receipt"]["retry_count"] == 2
    assert len(deps.agent_actions.list_agent_actions(agent_run_id=run["id"])) == 3


@pytest.mark.parametrize("failure", ["missing", "raises"])
def test_persistent_completion_failure_never_allows_retry(retry_api, tmp_path, failure):
    _, deps, run, action, _ = source(retry_api, tmp_path)

    def reader(**_):
        if failure == "raises":
            raise ValueError("completion corruption")
        return None

    service = OperatorConversationService(deps=deps, completion_reader=reader)
    for _ in range(2):
        result = service.respond(
            tenant_id=TENANT,
            principal_id=f"human:{USER}",
            session_user_id=USER,
            run_id=run["id"],
            message="Retry this action",
        )
        assert result["command_proposal"] is None
    assert_no_retry(deps, run, action)


def test_model_retry_intent_cannot_create_proposal(retry_api, tmp_path):
    _, deps, run, action, _ = source(retry_api, tmp_path)
    service = OperatorConversationService(
        deps=dataclasses.replace(
            deps, generate=lambda _: '{"intent":"retry_action","fact_ids":[]}'
        ),
        completion_reader=default_completion_coordinator(
            deps
        ).get_completion_read_model,
    )
    result = service.respond(
        tenant_id=TENANT,
        principal_id=f"human:{USER}",
        session_user_id=USER,
        run_id=run["id"],
        message="Explain this run",
    )
    assert result["intent"] == "explain_run"
    assert result["command_proposal"] is None
    assert_no_retry(deps, run, action)
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM operator_retry_proposals")
        .fetchone()[0]
        == 0
    )
