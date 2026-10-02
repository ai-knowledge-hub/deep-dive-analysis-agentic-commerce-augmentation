from __future__ import annotations

import dataclasses
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from api.main import app
from api.routes import operator_conversation
from domain.workflow.operator_commands import build_pause_proposal

from test_operator_conversation_api import (
    TENANT,
    USER,
    _action,
    _bff_headers,
    _command_headers,
    _post,
    _run,
    operator_api as _operator_api_fixture,
)


@pytest.fixture
def command_operator_api(tmp_path, monkeypatch):
    yield from _operator_api_fixture.__wrapped__(tmp_path, monkeypatch)


def test_operator_command_records_survive_reload_with_exact_receipt(
    command_operator_api,
):
    client, deps = command_operator_api
    run = _run(deps)
    proposal = _post(client, run["id"], message="Pause this run now").json()[
        "command_proposal"
    ]

    before = client.get(
        f"/conversation/operator/runs/{run['id']}/commands",
        headers=_bff_headers(run_id=run["id"]),
        params={"client_id": TENANT, "user_id": USER},
    )
    assert before.status_code == 200
    assert (
        before.json()["records"][0]["proposal"]["proposal_id"]
        == proposal["proposal_id"]
    )
    assert before.json()["records"][0]["receipt"] is None

    confirmed = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
        },
    )
    after = client.get(
        f"/conversation/operator/runs/{run['id']}/commands",
        headers=_bff_headers(run_id=run["id"]),
        params={"client_id": TENANT, "user_id": USER},
    )

    assert confirmed.status_code == 200
    assert after.status_code == 200
    record = after.json()["records"][0]
    assert record["proposal"]["proposal_digest"] == proposal["proposal_digest"]
    assert record["receipt"]["receipt_id"] == confirmed.json()["receipt"]["receipt_id"]
    assert (
        record["receipt"]["receipt_digest"]
        == confirmed.json()["receipt"]["receipt_digest"]
    )


def test_operator_command_records_page_without_silently_losing_old_evidence(
    command_operator_api,
):
    client, deps = command_operator_api
    run = _run(deps)
    first = _post(client, run["id"], message="Pause this run now").json()[
        "command_proposal"
    ]
    source = first["source"]
    latest_event = (
        {
            "id": source["latest_event_id"],
            "timestamp": source["latest_event_timestamp"],
        }
        if source["latest_event_id"]
        else None
    )
    issued = datetime.fromisoformat(first["issued_at"])
    for index in range(1, 53):
        proposal = build_pause_proposal(
            tenant_id=TENANT,
            principal_id=f"human:{USER}",
            run=run,
            snapshot_digest=source["snapshot_digest"],
            snapshot_cursor=source["snapshot_cursor"],
            latest_event=latest_event,
            preflight=first["preflight"]["result"],
            now=issued + timedelta(microseconds=index),
        )
        deps.operator_commands.create_proposal(
            proposal=proposal,
            current_snapshot_digest=lambda: source["snapshot_digest"],
        )

    cursor = None
    first_cursor = None
    proposal_ids: list[str] = []
    page_count = 0
    while True:
        params = {
            "client_id": TENANT,
            "user_id": USER,
            "limit": 7,
        }
        if cursor:
            params["cursor"] = cursor
        response = client.get(
            f"/conversation/operator/runs/{run['id']}/commands",
            headers=_bff_headers(run_id=run["id"]),
            params=params,
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["total_count"] == 53
        assert payload["page"]["total_count"] == 53
        assert payload["count"] == payload["page"]["returned_count"]
        proposal_ids.extend(
            record["proposal"]["proposal_id"] for record in payload["records"]
        )
        page_count += 1
        if not payload["page"]["has_more"]:
            assert payload["page"]["next_cursor"] is None
            break
        assert payload["completeness"]["state"] == "partial"
        cursor = payload["page"]["next_cursor"]
        first_cursor = first_cursor or cursor

    assert page_count == 8
    assert len(proposal_ids) == 53
    assert len(set(proposal_ids)) == 53

    other_run = _run(deps)
    wrong_scope = client.get(
        f"/conversation/operator/runs/{other_run['id']}/commands",
        headers=_bff_headers(run_id=other_run["id"]),
        params={
            "client_id": TENANT,
            "user_id": USER,
            "cursor": first_cursor,
        },
    )
    malformed = client.get(
        f"/conversation/operator/runs/{run['id']}/commands",
        headers=_bff_headers(run_id=run["id"]),
        params={"client_id": TENANT, "user_id": USER, "cursor": "not-a-cursor"},
    )
    assert wrong_scope.status_code == 400
    assert malformed.status_code == 400


def test_confirmation_rechecks_full_snapshot_inside_write_lock(
    command_operator_api,
):
    client, deps = command_operator_api
    run = _run(deps)
    action = _action(deps, run["id"])
    proposal = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    original_store = deps.operator_commands

    class RacingOperatorCommands:
        def __getattr__(self, name):
            return getattr(original_store, name)

        def commit_pause(self, **kwargs):
            from infrastructure.db.core.connection import get_connection

            conn = get_connection()
            conn.execute(
                """
                UPDATE agent_actions
                SET rationale_text = ?, updated_at = datetime('now')
                WHERE id = ? AND agent_run_id = ?
                """,
                ("Changed after route snapshot validation.", action["id"], run["id"]),
            )
            conn.commit()
            return original_store.commit_pause(**kwargs)

    raced_deps = dataclasses.replace(deps, operator_commands=RacingOperatorCommands())
    app.dependency_overrides[operator_conversation._deps] = lambda: raced_deps

    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "snapshot_changed"
    assert (
        deps.agent_runs.get_agent_run(run_id=run["id"], client_id=TENANT)["status"]
        == "running"
    )
    assert (
        original_store.get_receipt(
            proposal_id=proposal["proposal_id"],
            tenant_id=TENANT,
            workflow_id=run["id"],
        )
        is None
    )


def test_pause_commit_rolls_back_run_and_events_when_receipt_fails(
    command_operator_api,
):
    client, deps = command_operator_api
    run = _run(deps)
    proposal = _post(client, run["id"], message="Pause this workflow").json()[
        "command_proposal"
    ]
    preflight = proposal["preflight"]["result"]
    from infrastructure.db.core.connection import get_connection

    conn = get_connection()
    conn.execute(
        """
        CREATE TRIGGER fail_operator_receipt
        BEFORE INSERT ON operator_command_receipts
        BEGIN
            SELECT RAISE(ABORT, 'injected receipt failure');
        END
        """
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="injected receipt failure"):
        deps.operator_commands.commit_pause(
            proposal={
                key: value for key, value in proposal.items() if key != "consequences"
            },
            principal_id=f"human:{USER}",
            confirmation_state=lambda: {
                "snapshot_digest": proposal["source"]["snapshot_digest"],
                "preflight": preflight,
            },
        )

    assert (
        deps.agent_runs.get_agent_run(run_id=run["id"], client_id=TENANT)["status"]
        == "running"
    )
    events = deps.agent_events.list_agent_events(agent_run_id=run["id"], limit=100)
    assert not any(item["event_type"] == "operator_command_pause" for item in events)


def test_terminal_run_returns_blocked_pause_without_proposal(command_operator_api):
    client, deps = command_operator_api
    run = _run(deps, status="completed")

    response = _post(client, run["id"], message="Pause this run")

    assert response.status_code == 200
    assert response.json()["interaction_mode"] == "read_only"
    assert response.json()["command_proposal"] is None
    assert any(
        warning["code"] == "pause_preflight_blocked"
        for warning in response.json()["warnings"]
    )


def test_pause_proposal_and_receipt_rows_are_immutable(command_operator_api):
    client, deps = command_operator_api
    run = _run(deps)
    proposal = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
        },
    )
    receipt_id = response.json()["receipt"]["receipt_id"]
    from infrastructure.db.core.connection import get_connection

    conn = get_connection()
    with pytest.raises(sqlite3.IntegrityError, match="proposals are immutable"):
        conn.execute(
            "UPDATE operator_command_proposals SET expires_at = ? WHERE proposal_id = ?",
            ("2099-01-01T00:00:00+00:00", proposal["proposal_id"]),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="receipts are immutable"):
        conn.execute(
            "DELETE FROM operator_command_receipts WHERE receipt_id = ?",
            (receipt_id,),
        )
    conn.rollback()


def test_pause_confirmation_is_principal_bound(command_operator_api):
    client, deps = command_operator_api
    run = _run(deps)
    proposal = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    other_user = "other-operator"
    deps.users.ensure_user(other_user)
    deps.clients.add_client_user(client_id=TENANT, user_id=other_user, role="operator")

    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
            user_id=other_user,
        ),
        json={
            "client_id": TENANT,
            "user_id": other_user,
            "proposal_digest": proposal["proposal_digest"],
        },
    )

    assert response.status_code == 403
    assert (
        deps.agent_runs.get_agent_run(run_id=run["id"], client_id=TENANT)["status"]
        == "running"
    )


def test_expired_pause_proposal_fails_closed(command_operator_api, monkeypatch):
    client, deps = command_operator_api
    run = _run(deps)
    proposal = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    import domain.workflow.operator_commands as contract

    future = datetime.now(timezone.utc) + timedelta(hours=1)

    class FutureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return future if tz is not None else future.replace(tzinfo=None)

    monkeypatch.setattr(contract, "datetime", FutureDateTime)
    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "proposal_expired"
    assert (
        deps.agent_runs.get_agent_run(run_id=run["id"], client_id=TENANT)["status"]
        == "running"
    )


def test_pause_proposal_cannot_cross_run_or_digest(command_operator_api):
    client, deps = command_operator_api
    first = _run(deps)
    second = _run(deps)
    proposal = _post(client, first["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    forged_digest = "f" * 64

    wrong_run = client.post(
        f"/conversation/operator/runs/{second['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=second["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
        },
    )
    wrong_digest = client.post(
        f"/conversation/operator/runs/{first['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=first["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=forged_digest,
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": forged_digest,
        },
    )

    assert wrong_run.status_code == 404
    assert wrong_digest.status_code == 409
    assert all(
        deps.agent_runs.get_agent_run(run_id=item["id"], client_id=TENANT)["status"]
        == "running"
        for item in (first, second)
    )


def test_pause_receipt_links_operator_stopping_condition(command_operator_api):
    client, deps = command_operator_api
    run = _run(deps, harness_id="operator_supervised")
    proposal = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]

    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
        },
    )

    assert response.status_code == 200
    stop_id = response.json()["receipt"]["event_ids"]["stopping_condition"]
    stop = deps.agent_events.get_agent_event(event_id=stop_id)
    assert stop["event_type"] == "run_stopping_condition_met"
    assert stop["anchors"]["stopping_condition"] == "operator_pause"
    assert stop["anchors"]["receipt_id"] == response.json()["receipt"]["receipt_id"]


def test_pause_proposal_fails_closed_while_run_work_is_locked(command_operator_api):
    client, deps = command_operator_api
    run = _run(deps)
    assert deps.agent_runs.acquire_run_lock(
        run_id=run["id"], lock_token="in-flight-work", ttl_seconds=30
    )

    response = _post(client, run["id"], message="Pause this run")

    assert response.status_code == 200
    assert response.json()["command_proposal"] is None
    assert any(
        "locked work" in warning["message"]
        for warning in response.json()["warnings"]
        if warning["code"] == "pause_preflight_blocked"
    )
