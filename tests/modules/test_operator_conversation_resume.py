"""Resume invariants exercised through the authenticated API and durable store."""

from __future__ import annotations

import dataclasses
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from api.main import app
from api.routes import operator_conversation
from infrastructure.db.core.connection import get_connection
from test_operator_conversation_api import (
    TENANT,
    USER,
    _action,
    _bff_headers,
    _command_headers,
    _headers,
    _post,
    _run,
    operator_api as _operator_api_fixture,
)


@pytest.fixture
def resume_api(tmp_path, monkeypatch):
    yield from _operator_api_fixture.__wrapped__(tmp_path, monkeypatch)


def paused_run(deps, mode="auto_execute_safe", **kwargs):
    run = _run(deps, status="paused", **kwargs)
    return deps.agent_runs.update_agent_run(run_id=run["id"], run_mode=mode)


def propose(client, run):
    response = _post(client, run["id"], message="Resume this run")
    assert response.status_code == 200, response.text
    return response.json()["command_proposal"]


def confirm(client, run, proposal, *, command_type="resume", headers=None):
    return client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=headers
        or _command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
            command_type=command_type,
        ),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": command_type,
        },
    )


@pytest.mark.parametrize(
    ("mode", "target"), [("plan_only", "planned"), ("auto_execute_safe", "running")]
)
def test_resume_modes_proposal_confirmation_receipt_and_reload(
    resume_api, mode, target
):
    client, deps = resume_api
    run = paused_run(deps, mode)
    action = _action(deps, run["id"])
    proposal = propose(client, run)
    assert proposal["command_type"] == "resume"
    assert proposal["source"]["run_mode"] == mode
    assert proposal["predicted_run_status"] == target
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"
    response = confirm(client, run, proposal)
    assert response.status_code == 200, response.text
    receipt = response.json()["receipt"]
    assert receipt["resulting_run_status"] == target
    assert receipt["acknowledgement"] == "control_plane_resume_eligible"
    assert (
        deps.agent_actions.get_agent_action(action_id=action["id"])["status"]
        == "proposed"
    )
    events = deps.agent_events.list_agent_events(agent_run_id=run["id"], limit=100)
    assert [event["event_type"] for event in events] == [
        "operator_command_resume",
        "run_resumed",
    ]
    history = client.get(
        f"/conversation/operator/runs/{run['id']}/commands",
        headers=_bff_headers(run_id=run["id"]),
        params={"client_id": TENANT, "user_id": USER},
    ).json()
    assert (
        history["records"][0]["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    )


@pytest.mark.parametrize(
    "status",
    ["created", "planning", "planned", "running", "failed", "completed", "canceled"],
)
def test_resume_is_not_an_unrestricted_start(resume_api, status):
    client, deps = resume_api
    run = _run(deps, status=status)
    deps.agent_runs.update_agent_run(run_id=run["id"], run_mode="auto_execute_safe")
    assert propose(client, run) is None
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == status


@pytest.mark.parametrize(
    "mode", ["observe", "assist", "", "AUTO_EXECUTE_SAFE", "future_mode"]
)
def test_resume_rejects_unsupported_modes(resume_api, mode):
    client, deps = resume_api
    run = paused_run(deps, mode)
    assert propose(client, run) is None


def test_pause_and_read_assertions_cannot_confirm_resume(resume_api):
    client, deps = resume_api
    run = paused_run(deps)
    proposal = propose(client, run)
    assert confirm(client, run, proposal, command_type="pause").status_code == 409
    pause_headers = _command_headers(
        run_id=run["id"],
        proposal_id=proposal["proposal_id"],
        proposal_digest=proposal["proposal_digest"],
    )
    assert confirm(client, run, proposal, headers=pause_headers).status_code == 403
    assert (
        confirm(
            client, run, proposal, headers=_bff_headers(run_id=run["id"])
        ).status_code
        == 401
    )
    assert confirm(client, run, proposal, headers=_headers()).status_code == 403
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"


@pytest.mark.parametrize(
    "mutation",
    [
        "inputs",
        "budget",
        "authority",
        "mode",
        "revision",
        "policy",
        "registry",
        "cancel",
        "busy",
        "membership",
    ],
)
def test_resume_fences_changes_after_early_check_before_commit_lock(
    resume_api, mutation
):
    client, deps = resume_api
    run = paused_run(deps)
    action = _action(deps, run["id"])
    proposal = propose(client, run)
    original = deps.operator_commands

    class RacingStore:
        def __getattr__(self, name):
            return getattr(original, name)

        def commit_resume(self, **kwargs):
            conn = get_connection()
            queries = {
                "inputs": (
                    "UPDATE agent_actions SET inputs_json = json(?) WHERE id = ?",
                    ('{"changed":true}', action["id"]),
                ),
                "budget": (
                    "UPDATE agent_runs SET budgets_json = json(?) WHERE id = ?",
                    ('{"max_actions":0}', run["id"]),
                ),
                "authority": (
                    "UPDATE agent_runs SET allowed_capabilities_json = json(?) WHERE id = ?",
                    ('["run_variant"]', run["id"]),
                ),
                "mode": (
                    "UPDATE agent_runs SET run_mode = ? WHERE id = ?",
                    ("plan_only", run["id"]),
                ),
                "revision": (
                    "UPDATE agent_runs SET active_graph_revision = ? WHERE id = ?",
                    (2, run["id"]),
                ),
                "policy": (
                    "UPDATE agent_runs SET policy_profile_id = ? WHERE id = ?",
                    ("observe", run["id"]),
                ),
                "registry": (
                    "UPDATE agent_runs SET registry_fingerprint = ? WHERE id = ?",
                    ("changed", run["id"]),
                ),
                "cancel": (
                    "UPDATE agent_runs SET status = ? WHERE id = ?",
                    ("canceled", run["id"]),
                ),
                "busy": (
                    "UPDATE agent_runs SET lock_token = ? WHERE id = ?",
                    ("active-worker", run["id"]),
                ),
                "membership": (
                    "UPDATE client_users SET role = ? WHERE client_id = ? AND user_id = ?",
                    ("analyst", TENANT, USER),
                ),
            }
            conn.execute(*queries[mutation])
            conn.commit()
            return original.commit_resume(**kwargs)

    raced = dataclasses.replace(deps, operator_commands=RacingStore())
    app.dependency_overrides[operator_conversation._deps] = lambda: raced
    response = confirm(client, run, proposal)
    assert response.status_code == (403 if mutation == "membership" else 409), (
        response.text
    )
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == (
        "canceled" if mutation == "cancel" else "paused"
    )
    assert (
        original.get_receipt(
            proposal_id=proposal["proposal_id"], tenant_id=TENANT, workflow_id=run["id"]
        )
        is None
    )
    assert not any(
        e["event_type"] == "operator_command_resume"
        for e in deps.agent_events.list_agent_events(agent_run_id=run["id"])
    )


@pytest.mark.parametrize(
    "mutation", ["completion", "completion_tail", "live_registry"]
)
def test_resume_rechecks_derived_authority_under_commit_lock(
    resume_api, monkeypatch, mutation
):
    client, deps = resume_api
    run = paused_run(deps)
    view = {"authority_state": "legacy", "evidence": []}
    if mutation == "completion_tail":
        view["evidence"] = [
            {"evidence_id": f"evidence-{index}", "source_id": "original"}
            for index in range(30)
        ]

    class CompletionReader:
        def get_completion_read_model(self, **_kwargs):
            return dict(view)

    app.dependency_overrides[operator_conversation._completion_coordinator] = (
        CompletionReader
    )
    proposal = propose(client, run)
    original = deps.operator_commands

    class RacingStore:
        def __getattr__(self, name):
            return getattr(original, name)

        def commit_resume(self, **kwargs):
            if mutation == "completion":
                view["projection"] = {"state": "stale", "cursor": "advanced"}
            elif mutation == "completion_tail":
                view["evidence"][-1]["source_id"] = "substituted"
            else:
                monkeypatch.setattr(
                    "application.services.conversation.operator_resume.registry_contract_payload",
                    lambda: {"registry_version": "changed-live-registry"},
                )
            return original.commit_resume(**kwargs)

    app.dependency_overrides[operator_conversation._deps] = lambda: (
        dataclasses.replace(deps, operator_commands=RacingStore())
    )
    response = confirm(client, run, proposal)
    assert response.status_code == 409, response.text
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"
    assert original.get_receipt(
        proposal_id=proposal["proposal_id"], tenant_id=TENANT, workflow_id=run["id"]
    ) is None


def test_resume_receipt_failure_rolls_back_lifecycle_and_audits(resume_api):
    client, deps = resume_api
    run = paused_run(deps)
    proposal = propose(client, run)
    conn = get_connection()
    conn.execute(
        "CREATE TRIGGER fail_resume_receipt BEFORE INSERT ON operator_resume_receipts BEGIN SELECT RAISE(ABORT, 'injected receipt failure'); END"
    )
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected receipt failure"):
        confirm(client, run, proposal)
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"
    assert deps.agent_events.list_agent_events(agent_run_id=run["id"]) == []


def test_concurrent_resume_then_later_pause_replay_does_not_resume_again(resume_api):
    client, deps = resume_api
    run = paused_run(deps)
    proposal = propose(client, run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: confirm(client, run, proposal), range(2)))
    assert [r.status_code for r in responses] == [200, 200]
    assert len({r.json()["receipt"]["receipt_id"] for r in responses}) == 1
    paused = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert confirm(client, run, paused, command_type="pause").status_code == 200
    replay = confirm(client, run, proposal)
    assert replay.status_code == 200
    assert (
        replay.json()["receipt"]["receipt_digest"]
        == responses[0].json()["receipt"]["receipt_digest"]
    )
    assert replay.json()["run"]["status"] == "paused"
    events = deps.agent_events.list_agent_events(agent_run_id=run["id"])
    assert sum(e["event_type"] == "operator_command_resume" for e in events) == 1


def test_resume_clears_only_the_recorded_operator_pause_marker(resume_api):
    client, deps = resume_api
    run = paused_run(deps, "plan_only", harness_id="operator_supervised")
    deps.agent_runs.update_agent_run(run_id=run["id"], status="planned")
    pause = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    paused = confirm(client, run, pause, command_type="pause")
    assert paused.status_code == 200
    stop_id = paused.json()["receipt"]["event_ids"]["stopping_condition"]
    resume = propose(client, run)
    response = confirm(client, run, resume)
    assert response.status_code == 200, response.text
    clear = deps.agent_events.get_agent_event(
        event_id=response.json()["receipt"]["event_ids"]["stopping_condition"]
    )
    assert clear["event_type"] == "run_stopping_condition_cleared"
    assert clear["anchors"]["cleared_event_id"] == stop_id
    assert (
        deps.agent_events.get_agent_event(event_id=stop_id)["event_type"]
        == "run_stopping_condition_met"
    )


@pytest.mark.parametrize(
    "condition",
    [
        "budget_exhausted",
        "policy_block",
        "external_side_effect_required",
        "unknown_condition",
    ],
)
def test_recorded_other_stops_survive_a_new_operator_pause(resume_api, condition):
    client, deps = resume_api
    run = paused_run(deps)
    for marker in (condition, "operator_pause"):
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=None,
            sequence=0,
            event_type="run_stopping_condition_met",
            status="paused",
            anchors={"stopping_condition": marker},
        )
    assert propose(client, run) is None
    assert len(deps.agent_events.list_agent_events(agent_run_id=run["id"])) == 2


@pytest.mark.parametrize("blocker", ["budget", "policy", "external"])
def test_resume_recomputes_live_harness_stops(resume_api, blocker):
    client, deps = resume_api
    run = paused_run(deps, harness_id="safe_autonomy_b2b")
    action = _action(deps, run["id"])
    conn = get_connection()
    if blocker == "budget":
        conn.execute(
            "UPDATE agent_runs SET budgets_json = json('{\"max_actions\":0}') WHERE id = ?",
            (run["id"],),
        )
    elif blocker == "policy":
        conn.execute(
            "UPDATE agent_actions SET status = 'failed', error_text = 'Policy profile blocked action' WHERE id = ?",
            (action["id"],),
        )
    conn.commit()
    assert propose(client, run) is None


def test_resume_expiry_and_scope_substitution(resume_api, monkeypatch):
    from datetime import datetime, timedelta, timezone
    import domain.workflow.operator_commands as contract

    client, deps = resume_api
    run = paused_run(deps)
    proposal = propose(client, run)
    other = paused_run(deps)
    assert confirm(client, other, proposal).status_code == 404
    forged = {**proposal, "proposal_digest": "f" * 64}
    assert confirm(client, run, forged).status_code == 409
    outsider = "another-human"
    deps.users.ensure_user(outsider)
    deps.clients.add_client_user(client_id=TENANT, user_id=outsider, role="operator")
    assert (
        confirm(
            client,
            run,
            proposal,
            headers=_command_headers(
                run_id=run["id"],
                proposal_id=proposal["proposal_id"],
                proposal_digest=proposal["proposal_digest"],
                command_type="resume",
                user_id=outsider,
            ),
        ).status_code
        == 403
    )
    assert (
        confirm(
            client,
            run,
            proposal,
            headers=_command_headers(
                run_id=run["id"],
                proposal_id=proposal["proposal_id"],
                proposal_digest=proposal["proposal_digest"],
                command_type="resume",
                client_id="other-tenant",
            ),
        ).status_code
        == 403
    )
    future = datetime.now(timezone.utc) + timedelta(hours=1)

    class FutureDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return future

    monkeypatch.setattr(contract, "datetime", FutureDateTime)
    expired = confirm(client, run, proposal)
    assert expired.status_code == 409
    assert expired.json()["detail"]["code"] == "proposal_expired"
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"


def test_distinct_concurrent_resume_proposals_have_only_one_transition(resume_api):
    client, deps = resume_api
    run = paused_run(deps)
    proposals = [propose(client, run), propose(client, run)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda p: confirm(client, run, p), proposals))
    assert sorted(r.status_code for r in responses) == [200, 409]
    assert (
        sum(
            e["event_type"] == "run_resumed"
            for e in deps.agent_events.list_agent_events(agent_run_id=run["id"])
        )
        == 1
    )


def test_lost_acknowledgement_replays_in_a_fresh_process(resume_api):
    import json
    import subprocess
    import sys
    from shared.db import connection

    client, deps = resume_api
    run = paused_run(deps)
    proposal = propose(client, run)
    receipt = confirm(client, run, proposal).json()["receipt"]
    script = """
import json, sys
from api.composition import default_deps
from shared.db.connection import set_database_path
set_database_path(sys.argv[1])
deps = default_deps()
proposal = deps.operator_commands.get_proposal(proposal_id=sys.argv[2], tenant_id=sys.argv[3], workflow_id=sys.argv[4])
def forbidden():
    raise AssertionError('Replay attempted new admission')
receipt = deps.operator_commands.commit_resume(proposal=proposal, principal_id=proposal['principal_id'], confirmation_state=forbidden)
print(json.dumps(receipt))
"""
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            str(connection.DEFAULT_DB_PATH),
            proposal["proposal_id"],
            TENANT,
            run["id"],
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    replay = json.loads(result.stdout)
    assert replay["replayed"] is True
    assert replay["receipt_digest"] == receipt["receipt_digest"]


def test_mixed_pause_resume_history_retains_all_records_and_old_cursor(resume_api):
    client, deps = resume_api
    run = paused_run(deps)
    for _ in range(8):
        resume = propose(client, run)
        assert confirm(client, run, resume).status_code == 200
        pause = _post(client, run["id"], message="Pause this run").json()[
            "command_proposal"
        ]
        assert confirm(client, run, pause, command_type="pause").status_code == 200
    records = []
    cursor = None
    while True:
        page = deps.operator_commands.list_records(
            tenant_id=TENANT, workflow_id=run["id"], limit=3, cursor=cursor
        )
        assert page["page"]["total_count"] == 16
        records.extend(page["records"])
        cursor = page["page"]["next_cursor"]
        if not cursor:
            break
    assert len({r["proposal"]["proposal_id"] for r in records}) == 16
    assert {r["proposal"]["command_type"] for r in records} == {"pause", "resume"}
    assert all(r["receipt"] for r in records)


def test_resume_evidence_is_immutable(resume_api):
    client, deps = resume_api
    run = paused_run(deps)
    proposal = propose(client, run)
    response = confirm(client, run, proposal)
    conn = get_connection()
    for sql, identity in [
        (
            "DELETE FROM operator_resume_proposals WHERE proposal_id = ?",
            proposal["proposal_id"],
        ),
        (
            "UPDATE operator_resume_receipts SET acknowledgement = 'control_plane_paused' WHERE receipt_id = ?",
            response.json()["receipt"]["receipt_id"],
        ),
        (
            "DELETE FROM agent_events WHERE id = ?",
            response.json()["receipt"]["event_ids"]["command"],
        ),
    ]:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(sql, (identity,))
        conn.rollback()


def test_additive_migration_preserves_historical_pause_bytes_and_cursor(resume_api):
    from shared.db.migrations import apply_migrations

    client, deps = resume_api
    run = _run(deps)
    first = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    _post(client, run["id"], message="Pause this run")
    assert confirm(client, run, first, command_type="pause").status_code == 200
    conn = get_connection()
    before_proposals = [
        tuple(r)
        for r in conn.execute(
            "SELECT * FROM operator_command_proposals ORDER BY proposal_id"
        )
    ]
    before_receipts = [
        tuple(r)
        for r in conn.execute(
            "SELECT * FROM operator_command_receipts ORDER BY receipt_id"
        )
    ]
    cursor = deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run["id"], limit=1
    )["page"]["next_cursor"]
    # Remove only the empty expand-only schema, yielding an applied-056 database.
    for name in ("operator_all_proposals", "operator_all_receipts"):
        conn.execute(f"DROP VIEW {name}")
    for name in ("operator_resume_receipts", "operator_resume_proposals"):
        conn.execute(f"DROP TABLE {name}")
    for name in (
        "conversational_resume_audits_no_update",
        "conversational_resume_audits_no_delete",
        "conversational_resume_audits_no_replace",
    ):
        conn.execute(f"DROP TRIGGER {name}")
    conn.execute(
        "DELETE FROM schema_migrations WHERE name = '057_operator_conversation_resume_commands.sql'"
    )
    conn.commit()
    apply_migrations(conn)
    assert [
        tuple(r)
        for r in conn.execute(
            "SELECT * FROM operator_command_proposals ORDER BY proposal_id"
        )
    ] == before_proposals
    assert [
        tuple(r)
        for r in conn.execute(
            "SELECT * FROM operator_command_receipts ORDER BY receipt_id"
        )
    ] == before_receipts
    assert deps.operator_commands.list_records(
        tenant_id=TENANT, workflow_id=run["id"], limit=1, cursor=cursor
    )["records"]
    assert (
        confirm(client, run, first, command_type="pause").json()["receipt"]["replayed"]
        is True
    )
