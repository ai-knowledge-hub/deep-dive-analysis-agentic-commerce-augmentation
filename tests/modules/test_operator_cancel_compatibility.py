"""Cancel must coexist with immutable v1/v2 evidence and competing commands."""

from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from shared.db.migrations import apply_migrations
from infrastructure.db.core.connection import get_connection
from tests.modules.test_operator_conversation_cancel import (
    cancel_api as _cancel_api_fixture,
    eligible_run,
    propose_cancel,
    confirm_cancel,
)
from tests.modules.test_operator_conversation_resume import confirm, propose
from test_operator_conversation_api import TENANT, _post


@pytest.fixture
def cancel_api(tmp_path, monkeypatch):
    yield from _cancel_api_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize("other", ["pause", "resume"])
def test_cancel_competes_with_other_command_without_lost_update(cancel_api, other):
    client, deps = cancel_api
    run = eligible_run(deps, status="running" if other == "pause" else "paused")
    cancel = propose_cancel(client, run)
    competing = _post(client, run["id"], message=f"{other.title()} this run").json()[
        "command_proposal"
    ]
    assert competing is not None
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(confirm_cancel, client, run, cancel)
        second = pool.submit(confirm, client, run, competing, command_type=other)
        results = [first.result(), second.result()]
    assert sorted(r.status_code for r in results) == [200, 409]
    winner = next(r.json()["receipt"] for r in results if r.status_code == 200)
    assert (
        deps.agent_runs.get_agent_run(run_id=run["id"])["status"]
        == winner["resulting_run_status"]
    )
    receipts = (
        get_connection()
        .execute(
            "SELECT COUNT(*) FROM operator_all_receipts_v3 WHERE workflow_id = ?",
            (run["id"],),
        )
        .fetchone()[0]
    )
    assert receipts == 1


def test_migration_058_preserves_pause_resume_bytes_replay_and_cursor(cancel_api):
    client, deps = cancel_api
    run = eligible_run(deps)
    resume = propose(client, run)
    assert confirm(client, run, resume).status_code == 200
    pause = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert confirm(client, run, pause, command_type="pause").status_code == 200
    conn = get_connection()
    tables = (
        "operator_command_proposals",
        "operator_command_receipts",
        "operator_resume_proposals",
        "operator_resume_receipts",
    )
    before = {t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")] for t in tables}
    cursor = deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run["id"], limit=1
    )["page"]["next_cursor"]
    for view in ("operator_all_proposals_v3", "operator_all_receipts_v3"):
        conn.execute(f"DROP VIEW {view}")
    for table in ("operator_cancel_receipts", "operator_cancel_proposals"):
        conn.execute(f"DROP TABLE {table}")
    for suffix in ("no_update", "no_delete", "no_replace"):
        conn.execute(f"DROP TRIGGER conversational_cancel_audits_{suffix}")
    conn.execute(
        "DELETE FROM schema_migrations WHERE name = '058_operator_conversation_cancel_commands.sql'"
    )
    conn.commit()
    apply_migrations(conn)
    assert {
        t: [tuple(r) for r in conn.execute(f"SELECT * FROM {t}")] for t in tables
    } == before
    assert deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run["id"], limit=1, cursor=cursor
    )["records"]
    for command, proposal in (("resume", resume), ("pause", pause)):
        assert (
            confirm(client, run, proposal, command_type=command).json()["receipt"][
                "replayed"
            ]
            is True
        )
    cancel = propose_cancel(client, run)
    assert confirm_cancel(client, run, cancel).status_code == 200
    records = deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run["id"]
    )["records"]
    assert {r["proposal"]["command_type"] for r in records} == {
        "pause",
        "resume",
        "cancel",
    }
    assert all(r["receipt"] for r in records)
    # The prior backend's views must never receive rows it cannot deserialize.
    legacy_records = conn.execute(
        "SELECT proposal_json FROM operator_all_proposals"
    ).fetchall()
    import json

    assert {json.loads(r[0])["command_type"] for r in legacy_records} == {
        "pause",
        "resume",
    }
    assert conn.execute("SELECT COUNT(*) FROM operator_all_receipts").fetchone()[0] == 2
    assert (
        conn.execute("SELECT COUNT(*) FROM operator_all_receipts_v3").fetchone()[0] == 3
    )


@pytest.mark.parametrize(
    "table,identity",
    [
        ("operator_cancel_proposals", "proposal_id"),
        ("operator_cancel_receipts", "receipt_id"),
        ("agent_events", "id"),
    ],
)
@pytest.mark.parametrize("mutation", ["update", "delete", "replace"])
def test_cancel_evidence_cannot_be_mutated(cancel_api, table, identity, mutation):
    client, deps = cancel_api
    run = eligible_run(deps)
    proposal = propose_cancel(client, run)
    receipt = confirm_cancel(client, run, proposal).json()["receipt"]
    value = (
        proposal["proposal_id"]
        if table.endswith("proposals")
        else receipt["receipt_id"]
        if table.endswith("receipts")
        else receipt["event_ids"]["lifecycle"]
    )
    conn = get_connection()
    columns = ", ".join(r["name"] for r in conn.execute(f"PRAGMA table_info({table})"))
    statements = {
        "update": f"UPDATE {table} SET {identity} = {identity} WHERE {identity} = ?",
        "delete": f"DELETE FROM {table} WHERE {identity} = ?",
        "replace": f"INSERT OR REPLACE INTO {table} ({columns}) SELECT {columns} FROM {table} WHERE {identity} = ?",
    }
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(statements[mutation], (value,))
    conn.rollback()
    assert conn.execute(
        f"SELECT 1 FROM {table} WHERE {identity} = ?", (value,)
    ).fetchone()


def test_three_contract_history_pages_beyond_default_window(cancel_api):
    client, deps = cancel_api
    run = eligible_run(deps)
    for index in range(56):
        message = "Resume this run" if index % 2 else "Cancel this run"
        assert _post(client, run["id"], message=message).json()["command_proposal"]
    resume = propose(client, run)
    assert confirm(client, run, resume).status_code == 200
    pause = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert confirm(client, run, pause, command_type="pause").status_code == 200
    cursor, records = None, []
    while True:
        page = deps.operator_commands.list_records(
            tenant_id=TENANT, workflow_id=run["id"], limit=17, cursor=cursor
        )
        assert page["page"]["total_count"] == 58
        records.extend(page["records"])
        cursor = page["page"]["next_cursor"]
        if cursor is None:
            break
    assert len({r["proposal"]["proposal_id"] for r in records}) == 58
    assert {r["proposal"]["command_type"] for r in records} == {
        "pause",
        "resume",
        "cancel",
    }
    assert len([r for r in records if r["receipt"]]) == 2
