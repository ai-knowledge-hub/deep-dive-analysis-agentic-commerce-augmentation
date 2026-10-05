"""Regression evidence for commit failure isolation and exact target selection."""

import sqlite3

import pytest

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.transactions import JoinedTransaction
from tests.modules.test_approval_effect_authorization import (
    _approve,
    _additional_action,
)
from tests.modules.test_operator_action_review import (
    review_api as _review_fixture,
    review_run,
    assert_no_decision,
)
from test_operator_conversation_api import _post


@pytest.fixture
def review_api(tmp_path, monkeypatch):
    yield from _review_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize("error_type", [sqlite3.OperationalError, RuntimeError])
def test_standalone_approval_commit_failure_cannot_be_committed_by_later_writer(
    review_api, tmp_path, monkeypatch, error_type
):
    _, deps, run, action, _ = review_run(review_api, tmp_path)
    conn = get_connection()
    before = deps.agent_actions.get_agent_action(action_id=action["id"])
    error = error_type("injected standalone approval commit failure")

    class FailCommitOnce:
        failed = False

        def __getattr__(self, name):
            return getattr(conn, name)

        def commit(self):
            if not self.failed:
                self.failed = True
                raise error
            conn.commit()

    faulty_connection = FailCommitOnce()
    monkeypatch.setattr(
        "infrastructure.db.agent.approval_ledger.get_connection",
        lambda: faulty_connection,
    )
    with pytest.raises(error_type) as caught:
        _approve(deps, run, action)
    assert caught.value is error
    assert not conn.in_transaction
    deps.users.ensure_user("unrelated-later-writer")
    assert conn.execute(
        "SELECT id FROM users WHERE id='unrelated-later-writer'"
    ).fetchone()
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == before
    for table in (
        "approval_records",
        "approval_events",
        "approval_commands",
        "agent_events",
        "approval_effect_executions",
    ):
        assert conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_real_deferred_constraint_commit_failure_gets_full_owned_rollback():
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(
            "CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(parent_id INTEGER REFERENCES parent(id) DEFERRABLE INITIALLY DEFERRED);"
        )
        transaction = JoinedTransaction(conn, "deferred_approval")
        conn.execute("INSERT INTO child VALUES (42)")
        with pytest.raises(
            sqlite3.IntegrityError, match="FOREIGN KEY constraint failed"
        ):
            try:
                transaction.commit()
            except Exception:
                transaction.rollback()
                raise
        assert not conn.in_transaction
        conn.execute("INSERT INTO parent VALUES (42)")
        conn.commit()
        assert conn.execute("SELECT count(*) FROM child").fetchone()[0] == 0
    finally:
        conn.close()


@pytest.mark.parametrize("decision", ["Approve", "Reject"])
@pytest.mark.parametrize(
    "targets",
    [
        "action 1 and action 2",
        "action 1 and action 999",
        "action 1 and action missing",
        "action 1 and 2",
        "action 1,2",
        "action #1 and action number 2",
        "action 1 or action 2",
        "action {first} and action 2",
        "action {first} and action missing",
        "{first} and {second}",
        "{first} and 00000000-0000-0000-0000-000000000000",
        "actions 1 and 2",
    ],
)
def test_multiple_or_unresolved_review_targets_create_no_proposal(
    review_api, tmp_path, decision, targets
):
    client, deps, run, first, spec = review_run(review_api, tmp_path)
    second = _additional_action(deps, run, spec)
    response = _post(
        client,
        run["id"],
        message=f"{decision} {targets.format(first=first['id'], second=second['id'])}",
    )
    assert response.status_code == 200, response.text
    assert response.json()["command_proposal"] is None, response.json()
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_action_review_proposals")
        .fetchone()[0]
        == 0
    )
    assert_no_decision(deps, run, first)
    assert (
        deps.agent_actions.get_agent_action(action_id=second["id"])["status"]
        == "proposed"
    )


@pytest.mark.parametrize(
    "target",
    [
        "action 2",
        "action #2",
        "action number 2",
        "action {second}",
        "{second}",
        "action 2 and action {second}",
    ],
)
def test_single_exact_target_and_equivalent_references_remain_supported(
    review_api, tmp_path, target
):
    client, deps, run, first, spec = review_run(review_api, tmp_path)
    second = _additional_action(deps, run, spec)
    response = _post(
        client, run["id"], message=f"Approve {target.format(second=second['id'])}"
    )
    assert response.status_code == 200, response.text
    proposal = response.json()["command_proposal"]
    assert proposal["parameters"]["action_id"] == second["id"]
    assert_no_decision(deps, run, first)
