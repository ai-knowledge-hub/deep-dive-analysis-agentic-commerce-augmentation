"""Resume admission requires readable authority and event-specific stop resolution."""

from __future__ import annotations

import dataclasses

import pytest

from api.main import app
from api.routes import operator_conversation
from api.runtime_composition import default_completion_coordinator, default_runtime
from api.utils.principals import ensure_principal
from application.services.conversation.operator_resume import (
    build_resume_snapshot,
    conversational_resume_preflight,
)
from domain.workflow.operator_commands import build_resume_proposal
from infrastructure.db.core.connection import get_connection
from tests.modules.test_operator_conversation_resume import confirm, paused_run, propose
from test_operator_conversation_api import (
    TENANT,
    USER,
    _action,
    _post,
    operator_api as _operator_api_fixture,
)


@pytest.fixture
def integrity_api(tmp_path, monkeypatch):
    yield from _operator_api_fixture.__wrapped__(tmp_path, monkeypatch)


def stop(deps, run, condition):
    return deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=None,
        sequence=0,
        event_type="run_stopping_condition_met",
        status="paused",
        anchors={"stopping_condition": condition},
    )


def governed_run(deps):
    run = paused_run(deps)
    _action(deps, run["id"])
    coordinator = default_completion_coordinator(deps)
    token = "completion-test-lease"
    assert deps.agent_runs.acquire_run_lock(
        run_id=run["id"], lock_token=token, ttl_seconds=30
    )
    try:
        coordinator.synchronize_run(run_id=run["id"], lock_token=token)
    finally:
        deps.agent_runs.release_run_lock(run_id=run["id"], lock_token=token)
    deps.agent_runs.update_agent_run(run_id=run["id"], status="paused")
    view = coordinator.get_completion_read_model(
        tenant_id=TENANT, workflow_id=run["id"]
    )
    assert view["authoritative_decision"] is not None
    return run


def corrupt_completion(run, value="corrupted-a"):
    # Simulate damaged storage in this isolated database, beyond SQL write guards.
    conn = get_connection()
    conn.execute("DROP TRIGGER IF EXISTS workflow_completion_decisions_no_update")
    conn.execute(
        "UPDATE workflow_completion_decisions SET decision_digest = ? WHERE workflow_id = ?",
        (value, run["id"]),
    )
    conn.commit()


def assert_no_resume(deps, run):
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == "paused"
    conn = get_connection()
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM operator_resume_receipts WHERE workflow_id = ?",
            (run["id"],),
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE agent_run_id = ? AND event_type IN ('operator_command_resume', 'run_resumed')",
            (run["id"],),
        ).fetchone()[0]
        == 0
    )


def test_persistently_corrupt_completion_blocks_new_proposals(integrity_api):
    client, deps = integrity_api
    run = governed_run(deps)
    for value in ("corrupted-a", "corrupted-b"):
        corrupt_completion(run, value)
        response = _post(client, run["id"], message="Resume this run")
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["snapshot"]["completion"]["state"] == "unavailable"
        assert any(
            w["code"] == "completion_integrity_unavailable" for w in body["warnings"]
        )
        assert body["command_proposal"] is None
        assert "completion" in body["answer"].lower()
        assert_no_resume(deps, run)
    assert (
        get_connection()
        .execute(
            "SELECT COUNT(*) FROM operator_resume_proposals WHERE workflow_id = ?",
            (run["id"],),
        )
        .fetchone()[0]
        == 0
    )


def test_preexisting_unverified_proposal_cannot_commit_with_stable_bad_snapshot(
    integrity_api,
):
    client, deps = integrity_api
    ensure_principal(
        principal_id=f"human:{USER}", principal_type="human", tenant_id=TENANT
    )
    run = governed_run(deps)
    corrupt_completion(run)
    coordinator = default_completion_coordinator(deps)

    def snapshot():
        return build_resume_snapshot(
            deps=deps,
            completion_reader=coordinator.get_completion_read_model,
            tenant_id=TENANT,
            principal_id=f"human:{USER}",
            run_id=run["id"],
        )

    before = snapshot()
    preflight = conversational_resume_preflight(
        deps=deps, tenant_id=TENANT, run_id=run["id"], snapshot=before
    )
    # Persist a proposal from a producer with the original unsafe admission
    # contract; final admission must reject it even if its snapshot is stable.
    preflight.pop("completion_verified")
    preflight.update(
        allowed=True, blockers=[], summary="Resume will return this run to running."
    )
    proposal = build_resume_proposal(
        tenant_id=TENANT,
        principal_id=f"human:{USER}",
        run=deps.agent_runs.get_agent_run(run_id=run["id"]),
        snapshot_digest=before["snapshot_digest"],
        snapshot_cursor=before["event_page"].get("after_cursor"),
        latest_event=before["events"][-1] if before["events"] else None,
        preflight=preflight,
    )
    deps.operator_commands.create_proposal(
        proposal=proposal, current_snapshot_digest=lambda: snapshot()["snapshot_digest"]
    )
    corrupt_completion(run, "corrupted-b")
    assert snapshot()["snapshot_digest"] == before["snapshot_digest"]
    response = confirm(client, run, proposal)
    assert response.status_code == 409, response.text
    assert_no_resume(deps, run)


@pytest.mark.parametrize("fault_point", ["before_confirmation", "under_commit_lock"])
def test_completion_corruption_after_proposal_cannot_commit(integrity_api, fault_point):
    client, deps = integrity_api
    run = governed_run(deps)
    proposal = propose(client, run)
    original = deps.operator_commands
    if fault_point == "before_confirmation":
        corrupt_completion(run)
    else:

        class RacingStore:
            def __getattr__(self, name):
                return getattr(original, name)

            def commit_resume(self, **kwargs):
                corrupt_completion(run)
                return original.commit_resume(**kwargs)

        app.dependency_overrides[operator_conversation._deps] = lambda: (
            dataclasses.replace(deps, operator_commands=RacingStore())
        )
    response = confirm(client, run, proposal)
    assert response.status_code == 409, response.text
    assert_no_resume(deps, run)


@pytest.mark.parametrize("failure", ["missing", "exception"])
def test_unverified_completion_is_not_legacy_compatibility(integrity_api, failure):
    client, deps = integrity_api
    run = paused_run(deps)

    class CompletionReader:
        def get_completion_read_model(self, **_):
            if failure == "exception":
                raise ValueError("private storage details must stay private")
            return None

    app.dependency_overrides[operator_conversation._completion_coordinator] = (
        CompletionReader
    )
    response = _post(client, run["id"], message="Resume this run")
    assert response.status_code == 200
    assert response.json()["command_proposal"] is None
    assert "private storage details" not in response.text
    assert_no_resume(deps, run)


@pytest.mark.parametrize("mode", ["plan_only", "auto_execute_safe"])
def test_verified_legacy_completion_remains_resumable(integrity_api, mode):
    client, deps = integrity_api
    run = paused_run(deps, mode)
    view = default_completion_coordinator(deps).get_completion_read_model(
        tenant_id=TENANT, workflow_id=run["id"]
    )
    assert view["authority_state"] == "legacy"
    assert view["completion_authority_required"] is False
    assert confirm(client, run, propose(client, run)).status_code == 200


@pytest.mark.parametrize("replay_path", ["fast_read", "commit_lock"])
def test_receipt_replay_survives_later_completion_corruption(
    integrity_api, replay_path
):
    client, deps = integrity_api
    run = governed_run(deps)
    proposal = propose(client, run)
    committed = confirm(client, run, proposal)
    assert committed.status_code == 200, committed.text
    deps.agent_runs.update_agent_run(run_id=run["id"], status="paused")
    corrupt_completion(run)
    if replay_path == "commit_lock":
        original = deps.operator_commands

        class StaleReceiptRead:
            def __getattr__(self, name):
                return getattr(original, name)

            def get_receipt(self, **_):
                # Another exact confirmation may commit after the early read.
                return None

        app.dependency_overrides[operator_conversation._deps] = lambda: (
            dataclasses.replace(deps, operator_commands=StaleReceiptRead())
        )
    replay = confirm(client, run, proposal)
    assert replay.status_code == 200, replay.text
    assert replay.json()["receipt"]["replayed"] is True
    assert {k: v for k, v in replay.json()["receipt"].items() if k != "replayed"} == {
        k: v for k, v in committed.json()["receipt"].items() if k != "replayed"
    }
    assert replay.json()["run"]["status"] == "paused"


@pytest.mark.parametrize(
    "condition", ["policy_block", "budget_exhausted", "unknown_condition"]
)
def test_legacy_start_does_not_clear_an_unresolved_stop(integrity_api, condition):
    client, deps = integrity_api
    run = paused_run(deps)
    marker = stop(deps, run, condition)
    # Exercise the compatibility writer, then a real conversational pause.
    default_runtime(deps).start_run(run_id=run["id"])
    pause = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert confirm(client, run, pause, command_type="pause").status_code == 200
    assert propose(client, run) is None
    assert_no_resume(deps, run)
    assert (
        deps.agent_events.get_agent_event(event_id=marker["id"])["event_type"]
        == "run_stopping_condition_met"
    )


@pytest.mark.parametrize(
    "resolution", ["exact", "other_event", "before_stop", "other_run"]
)
def test_only_later_same_run_exact_clear_resolves_stop_across_start(
    integrity_api, resolution
):
    client, deps = integrity_api
    run = paused_run(deps)
    marker = stop(deps, run, "policy_block")
    default_runtime(deps).start_run(run_id=run["id"])
    pause = _post(client, run["id"], message="Pause this run").json()[
        "command_proposal"
    ]
    assert confirm(client, run, pause, command_type="pause").status_code == 200
    clear = deps.agent_events.create_agent_event(
        agent_run_id=paused_run(deps)["id"] if resolution == "other_run" else run["id"],
        action_id=None,
        sequence=0,
        event_type="run_stopping_condition_cleared",
        status="paused",
        anchors={
            "cleared_event_id": marker["id"]
            if resolution != "other_event"
            else "unrelated"
        },
    )
    if resolution == "before_stop":
        # Reinsert the stop after a clear referring to its future ID.
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM agent_events WHERE id = ?", (marker["id"],)
        ).fetchone()
        conn.execute("DELETE FROM agent_events WHERE id = ?", (marker["id"],))
        fields = list(row.keys())
        conn.execute(
            f"INSERT INTO agent_events ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            tuple(row),
        )
        conn.commit()
    proposal = propose(client, run)
    if resolution == "exact":
        assert proposal is not None
        assert confirm(client, run, proposal).status_code == 200
    else:
        assert proposal is None
        assert_no_resume(deps, run)
    assert deps.agent_events.get_agent_event(event_id=clear["id"]) is not None


def test_start_cannot_hide_truncated_stop_history(integrity_api):
    client, deps = integrity_api
    run = paused_run(deps)
    stop(deps, run, "policy_block")
    for _ in range(501):
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=None,
            sequence=0,
            event_type="run_started",
            status="running",
            anchors={},
        )
    response = _post(client, run["id"], message="Resume this run")
    assert response.status_code == 200
    assert response.json()["command_proposal"] is None
    assert "history is incomplete" in response.json()["answer"]
    assert_no_resume(deps, run)


def test_complete_history_at_confirmation_bound_remains_resumable(integrity_api):
    client, deps = integrity_api
    run = paused_run(deps)
    for _ in range(500):
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=None,
            sequence=0,
            event_type="run_started",
            status="running",
            anchors={},
        )
    proposal = propose(client, run)
    assert proposal is not None
    assert confirm(client, run, proposal).status_code == 200
