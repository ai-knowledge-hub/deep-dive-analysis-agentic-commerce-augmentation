"""Exact, terminal cancellation through authenticated chat and durable receipts."""

from __future__ import annotations

import dataclasses
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from api.main import app
from api.routes import operator_conversation
from api.runtime_composition import default_runtime
from tests.modules.test_operator_conversation_resume import confirm
from tests.modules.test_operator_resume_admission_integrity import (
    corrupt_completion,
    governed_run,
)
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
from infrastructure.db.core.connection import get_connection


@pytest.fixture
def cancel_api(tmp_path, monkeypatch):
    yield from _operator_api_fixture.__wrapped__(tmp_path, monkeypatch)


def eligible_run(deps, *, status="paused", mode="auto_execute_safe", **kwargs):
    run = _run(deps, status=status, **kwargs)
    return deps.agent_runs.update_agent_run(run_id=run["id"], run_mode=mode)


def propose_cancel(client, run):
    response = _post(client, run["id"], message="Cancel this run")
    assert response.status_code == 200, response.text
    return response.json()["command_proposal"]


def confirm_cancel(client, run, proposal, **kwargs):
    return confirm(client, run, proposal, command_type="cancel", **kwargs)


def assert_not_canceled(deps, run):
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["status"] == run["status"]
    assert (
        get_connection()
        .execute(
            "SELECT COUNT(*) FROM operator_cancel_receipts WHERE workflow_id = ?",
            (run["id"],),
        )
        .fetchone()[0]
        == 0
    )
    assert (
        get_connection()
        .execute(
            "SELECT COUNT(*) FROM agent_events WHERE agent_run_id = ? AND event_type IN ('operator_command_cancel', 'run_canceled')",
            (run["id"],),
        )
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    "status", ["created", "planning", "planned", "running", "paused"]
)
@pytest.mark.parametrize("mode", ["plan_only", "auto_execute_safe"])
def test_cancel_source_matrix_terminal_receipt_and_reload(cancel_api, status, mode):
    client, deps = cancel_api
    run = eligible_run(deps, status=status, mode=mode)
    action = _action(deps, run["id"])
    proposal = propose_cancel(client, run)
    assert proposal["contract"] == "workflow.operator-command-proposal.v3"
    assert proposal["source"]["run_mode"] == mode
    assert proposal["predicted_run_status"] == "canceled"
    assert_not_canceled(deps, run)
    response = confirm_cancel(client, run, proposal)
    assert response.status_code == 200, response.text
    receipt = response.json()["receipt"]
    assert receipt["contract"] == "workflow.operator-command-receipt.v3"
    assert receipt["acknowledgement"] == "control_plane_canceled"
    assert receipt["resulting_run_status"] == "canceled"
    assert receipt["event_ids"]["stopping_condition"] is None
    assert receipt["run_mode"] == mode
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) == action
    persisted = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert persisted["status"] == "canceled"
    assert persisted["run_mode"] == mode
    assert persisted["state"] == run["state"]
    events = deps.agent_events.list_agent_events(agent_run_id=run["id"])
    assert [e["event_type"] for e in events] == [
        "operator_command_cancel",
        "run_canceled",
    ]
    history = client.get(
        f"/conversation/operator/runs/{run['id']}/commands",
        headers=_bff_headers(run_id=run["id"]),
        params={"client_id": TENANT, "user_id": USER},
    )
    assert history.status_code == 200
    assert (
        history.json()["records"][0]["receipt"]["receipt_digest"]
        == receipt["receipt_digest"]
    )
    replay = confirm_cancel(client, run, proposal)
    assert replay.status_code == 200
    assert replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    assert len(deps.agent_events.list_agent_events(agent_run_id=run["id"])) == 2
    for command in ("Resume this run", "Pause this run", "Cancel this run"):
        assert (
            _post(client, run["id"], message=command).json()["command_proposal"] is None
        )
    for command in ("start", "retry", "change_plan"):
        from application.services.agent_runtime.commands import (
            preflight_agent_run_command,
        )

        preflight = preflight_agent_run_command(
            deps=deps,
            run_id=run["id"],
            client_id=TENANT,
            command_type=command,
            action_id=action["id"] if command == "retry" else None,
            metadata={},
        )
        assert preflight["preflight"]["allowed"] is False


@pytest.mark.parametrize(
    "status", ["failed", "completed", "canceled", "cancelled", "unknown", "PAUSED"]
)
def test_cancel_rejects_terminal_unknown_or_noncanonical_sources(cancel_api, status):
    client, deps = cancel_api
    run = eligible_run(deps, status=status)
    assert propose_cancel(client, run) is None
    assert_not_canceled(deps, run)


@pytest.mark.parametrize(
    "mode", ["observe", "auto_execute", "PLAN_ONLY", "", "future_mode"]
)
def test_cancel_rejects_unsupported_modes(cancel_api, mode):
    client, deps = cancel_api
    run = eligible_run(deps, mode=mode)
    assert propose_cancel(client, run) is None
    assert_not_canceled(deps, run)


@pytest.mark.parametrize(
    "stop", ["policy_block", "budget_exhausted", "operator_pause", "unknown_condition"]
)
def test_cancel_preserves_unresolved_stops_without_blocking_terminal_exit(
    cancel_api, stop
):
    client, deps = cancel_api
    run = eligible_run(deps, harness_id="safe_autonomy_b2b")
    marker = deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=None,
        sequence=0,
        event_type="run_stopping_condition_met",
        status="paused",
        anchors={"stopping_condition": stop},
    )
    # Effective harness budget exhaustion must not turn cancellation into resume admission.
    get_connection().execute(
        "UPDATE agent_runs SET budgets_json = json('{\"max_actions\":0}') WHERE id = ?",
        (run["id"],),
    )
    get_connection().commit()
    proposal = propose_cancel(client, run)
    assert proposal is not None
    response = confirm_cancel(client, run, proposal)
    assert response.status_code == 200, response.text
    assert deps.agent_events.get_agent_event(event_id=marker["id"]) == marker
    assert not any(
        e["event_type"] == "run_stopping_condition_cleared"
        for e in deps.agent_events.list_agent_events(agent_run_id=run["id"])
    )


@pytest.mark.parametrize("blocker", ["lock", "executing", "oversized_actions"])
def test_cancel_requires_quiescent_complete_control_state(cancel_api, blocker):
    client, deps = cancel_api
    run = eligible_run(deps)
    if blocker == "lock":
        assert deps.agent_runs.acquire_run_lock(
            run_id=run["id"], lock_token="worker", ttl_seconds=30
        )
    elif blocker == "executing":
        action = _action(deps, run["id"])
        deps.agent_actions.update_agent_action_status(
            action_id=action["id"], status="executing"
        )
    else:
        # An adapter may return the MAX_ACTIONS+1 sentinel. No hidden tail can certify quiescence.
        original = deps.agent_actions
        action = _action(deps, run["id"])

        class ManyActions:
            def __getattr__(self, name):
                return getattr(original, name)

            def list_agent_actions(self, **_):
                return [action] * 501

        app.dependency_overrides[operator_conversation._deps] = lambda: (
            dataclasses.replace(deps, agent_actions=ManyActions())
        )
    assert propose_cancel(client, run) is None
    assert_not_canceled(deps, run)


@pytest.mark.parametrize(
    "fault_point", ["before_proposal", "before_confirm", "under_lock"]
)
def test_corrupt_completion_never_authorizes_cancel(cancel_api, fault_point):
    client, deps = cancel_api
    run = governed_run(deps)
    original = deps.operator_commands
    if fault_point == "before_proposal":
        corrupt_completion(run)
        assert propose_cancel(client, run) is None
    else:
        proposal = propose_cancel(client, run)
        if fault_point == "before_confirm":
            corrupt_completion(run)
        else:

            class RacingStore:
                def __getattr__(self, name):
                    return getattr(original, name)

                def commit_cancel(self, **kwargs):
                    corrupt_completion(run)
                    return original.commit_cancel(**kwargs)

            app.dependency_overrides[operator_conversation._deps] = lambda: (
                dataclasses.replace(deps, operator_commands=RacingStore())
            )
        assert confirm_cancel(client, run, proposal).status_code == 409
    assert_not_canceled(deps, run)


@pytest.mark.parametrize(
    "mutation",
    [
        "inputs",
        "mode",
        "revision",
        "policy",
        "lock",
        "membership",
        "validation",
        "registry",
    ],
)
def test_cancel_revalidates_evidence_after_route_early_read(
    cancel_api, monkeypatch, mutation
):
    client, deps = cancel_api
    run = eligible_run(deps)
    action = _action(deps, run["id"])
    proposal = propose_cancel(client, run)
    original = deps.operator_commands

    class RacingStore:
        def __getattr__(self, name):
            return getattr(original, name)

        def commit_cancel(self, **kwargs):
            conn = get_connection()
            if mutation == "inputs":
                conn.execute(
                    "UPDATE agent_actions SET inputs_json = json('{\"changed\":true}') WHERE id = ?",
                    (action["id"],),
                )
            elif mutation == "membership":
                conn.execute(
                    "UPDATE client_users SET role = 'analyst' WHERE client_id = ? AND user_id = ?",
                    (TENANT, USER),
                )
            elif mutation == "registry":
                monkeypatch.setattr(
                    "application.services.conversation.operator_cancel.registry_contract_payload",
                    lambda: {"registry_version": "changed"},
                )
            elif mutation == "validation":
                conn.execute(
                    'UPDATE agent_actions SET outputs_json = json(\'{"validation_job_id":"substituted"}\') WHERE id = ?',
                    (action["id"],),
                )
            else:
                updates = {
                    "mode": ("run_mode", "plan_only"),
                    "revision": ("active_graph_revision", 2),
                    "policy": ("policy_profile_id", "observe"),
                    "lock": ("lock_token", "worker"),
                }
                field, value = updates[mutation]
                conn.execute(
                    f"UPDATE agent_runs SET {field} = ? WHERE id = ?",
                    (value, run["id"]),
                )
            conn.commit()
            return original.commit_cancel(**kwargs)

    app.dependency_overrides[operator_conversation._deps] = lambda: dataclasses.replace(
        deps, operator_commands=RacingStore()
    )
    response = confirm_cancel(client, run, proposal)
    assert response.status_code in {403, 409}, response.text
    assert_not_canceled(deps, run)


@pytest.mark.parametrize("wrong_type", ["pause", "resume"])
def test_cancel_cannot_use_another_command_assertion(cancel_api, wrong_type):
    client, deps = cancel_api
    run = eligible_run(deps)
    proposal = propose_cancel(client, run)
    response = confirm_cancel(
        client,
        run,
        proposal,
        headers=_command_headers(
            run_id=run["id"],
            proposal_id=proposal["proposal_id"],
            proposal_digest=proposal["proposal_digest"],
            command_type=wrong_type,
        ),
    )
    assert response.status_code == 403
    assert_not_canceled(deps, run)


def test_cancel_read_assertion_cannot_confirm(cancel_api):
    client, deps = cancel_api
    run = eligible_run(deps)
    proposal = propose_cancel(client, run)
    assert (
        confirm_cancel(
            client, run, proposal, headers=_bff_headers(run_id=run["id"])
        ).status_code
        == 401
    )
    assert_not_canceled(deps, run)


@pytest.mark.parametrize("failure", ["receipt", "workflow_projection"])
def test_cancel_failure_rolls_back_status_audits_and_receipt(cancel_api, failure):
    client, deps = cancel_api
    run = eligible_run(deps)
    if failure == "workflow_projection":
        get_connection().execute(
            "UPDATE agent_runs SET harness_id = 'safe_autonomy_b2b', policy_profile_id = 'human_approval_required', registry_version = 'test-v1', registry_fingerprint = 'test-fingerprint', trace_id = 'test-trace' WHERE id = ?",
            (run["id"],),
        )
        get_connection().commit()
        deps.workflow_compatibility.project_sequential_run(
            tenant_id=TENANT, run_id=run["id"]
        )
    proposal = propose_cancel(client, run)
    table = (
        "operator_cancel_receipts"
        if failure == "receipt"
        else "workflow_compatibility_events"
    )
    guard = (
        ""
        if failure == "receipt"
        else "WHEN NEW.event_type = 'compatibility.agent.run_canceled'"
    )
    get_connection().execute(
        f"CREATE TRIGGER cancel_fail BEFORE INSERT ON {table} {guard} BEGIN SELECT RAISE(ABORT, 'injected cancellation failure'); END"
    )
    get_connection().commit()
    with pytest.raises(sqlite3.IntegrityError, match="injected cancellation failure"):
        confirm_cancel(client, run, proposal)
    assert_not_canceled(deps, run)
    if failure == "workflow_projection":
        assert (
            get_connection()
            .execute(
                "SELECT COUNT(*) FROM workflow_compatibility_events WHERE workflow_id = ?",
                (run["id"],),
            )
            .fetchone()[0]
            == 0
        )


def test_concurrent_exact_cancel_returns_one_receipt(cancel_api):
    client, deps = cancel_api
    run = eligible_run(deps)
    proposal = propose_cancel(client, run)
    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(
            pool.map(lambda _: confirm_cancel(client, run, proposal), range(2))
        )
    assert [r.status_code for r in responses] == [200, 200]
    assert len({r.json()["receipt"]["receipt_id"] for r in responses}) == 1
    assert len(deps.agent_events.list_agent_events(agent_run_id=run["id"])) == 2


@pytest.mark.parametrize("replay_path", ["fast_read", "commit_lock"])
def test_cancel_receipt_replays_after_corruption(cancel_api, replay_path):
    client, deps = cancel_api
    run = governed_run(deps)
    proposal = propose_cancel(client, run)
    first = confirm_cancel(client, run, proposal)
    assert first.status_code == 200, first.text
    corrupt_completion(run)
    if replay_path == "commit_lock":
        original = deps.operator_commands

        class StaleReceiptRead:
            def __getattr__(self, name):
                return getattr(original, name)

            def get_receipt(self, **_):
                return None

        app.dependency_overrides[operator_conversation._deps] = lambda: (
            dataclasses.replace(deps, operator_commands=StaleReceiptRead())
        )
    replay = confirm_cancel(client, run, proposal)
    assert replay.status_code == 200, replay.text
    assert (
        replay.json()["receipt"]["receipt_digest"]
        == first.json()["receipt"]["receipt_digest"]
    )
    assert replay.json()["run"]["status"] == "canceled"
    assert_not_revivable = default_runtime(deps)
    from application.services.agent_runtime.runtime import AgentRuntimeError

    with pytest.raises(AgentRuntimeError):
        assert_not_revivable.start_run(run_id=run["id"])


@pytest.mark.parametrize("reader_state", ["missing", "raises"])
def test_cancel_requires_successful_completion_reader(cancel_api, reader_state):
    from application.services.conversation.operator_gateway import (
        OperatorConversationService,
    )

    _, deps = cancel_api
    run = eligible_run(deps)

    def reader(**_):
        if reader_state == "raises":
            raise RuntimeError("completion integrity failure")
        return None

    service = OperatorConversationService(deps=deps, completion_reader=reader)
    for _ in range(2):
        result = service.respond(
            tenant_id=TENANT,
            principal_id=f"human:{USER}",
            session_user_id=USER,
            run_id=run["id"],
            message="Cancel this run",
        )
        assert result["command_proposal"] is None
    assert_not_canceled(deps, run)


@pytest.mark.parametrize("substitution", ["run", "tenant", "principal", "digest"])
def test_cancel_confirmation_assertion_is_bound_to_exact_scope(
    cancel_api, substitution
):
    client, deps = cancel_api
    run = eligible_run(deps)
    proposal = propose_cancel(client, run)
    bindings = {
        "run_id": run["id"],
        "proposal_id": proposal["proposal_id"],
        "proposal_digest": proposal["proposal_digest"],
        "command_type": "cancel",
    }
    if substitution == "run":
        bindings["run_id"] = "another-run"
    elif substitution == "tenant":
        bindings["client_id"] = "another-tenant"
    elif substitution == "principal":
        bindings["user_id"] = "another-user"
    else:
        bindings["proposal_digest"] = "0" * 64
    response = confirm_cancel(
        client, run, proposal, headers=_command_headers(**bindings)
    )
    assert response.status_code == 403
    assert_not_canceled(deps, run)
