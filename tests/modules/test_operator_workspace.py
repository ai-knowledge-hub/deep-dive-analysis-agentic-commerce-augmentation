"""Durable creation authority, transaction failure and conversation continuity."""

import pytest
from tests.test_operator_conversation_api import (
    operator_api as _fixture,
    _headers,
    TENANT,
    USER,
)
from infrastructure.db.core.connection import get_connection


@pytest.fixture
def workspace_api(tmp_path, monkeypatch):
    from api.main import app
    from api.routes import operator_workspace
    from api.runtime_composition import default_completion_coordinator

    fixture = _fixture.__wrapped__(tmp_path, monkeypatch)
    client, deps = next(fixture)
    app.dependency_overrides[operator_workspace._deps] = lambda: deps
    app.dependency_overrides[operator_workspace._completion_coordinator] = lambda: (
        default_completion_coordinator(deps)
    )
    try:
        yield client, deps
    finally:
        fixture.close()


def experiment(deps, name="Commerce optimisation", *, control=True):
    battery = deps.query_batteries.create_battery(
        client_id=TENANT, product_id="product-1", name="Queries"
    )
    deps.query_batteries.add_query(
        battery_id=battery["id"], query_text="Which product best fits this goal?"
    )
    created = deps.experiments.create_experiment(
        client_id=TENANT,
        product_id="product-1",
        brand_id="brand-1",
        battery_id=battery["id"],
        name=name,
    )
    if control:
        deps.experiments.add_variant(
            experiment_id=created["id"],
            client_id=TENANT,
            label="Control",
            variant_type="baseline",
            payload={"role": "control", "copy": "original"},
        )
    return created


def prepare(client, **overrides):
    return client.post(
        "/conversation/operator/workspaces/message",
        headers=_headers(),
        json={
            "client_id": TENANT,
            "message": "Improve commerce performance",
            **overrides,
        },
    )


def confirm(client, prepared, headers=None):
    proposal = prepared["proposal"]
    return client.post(
        f"/conversation/operator/workspaces/{prepared['session_id']}/proposals/{proposal['proposal_id']}/confirm",
        headers=headers or _headers(scopes=["agent_runs:read", "agent_runs:write"]),
        json={"client_id": TENANT, "proposal_digest": proposal["proposal_digest"]},
    )


def counts():
    conn = get_connection()
    return {
        table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        for table in (
            "agent_runs",
            "agent_actions",
            "agent_events",
            "workflow_completion_governance",
            "workflow_outcome_commands",
            "workflow_compatibility_runs",
            "workflow_compatibility_revision_tasks",
            "workflow_completion_criteria",
            "workflow_completion_task_definitions",
            "workflow_completion_attempt_authorities",
            "operator_run_creation_receipts",
            "approval_effect_executions",
            "approval_commands",
        )
    }


def test_preparation_creation_replay_and_same_conversation(workspace_api):
    client, deps = workspace_api
    experiment(deps)
    before = counts()
    prepared = prepare(client)
    assert prepared.status_code == 200, prepared.text
    assert counts() == before
    prepared = prepared.json()
    assert prepared["state"] == "proposed"
    result = confirm(client, prepared)
    assert result.status_code == 200, result.text
    result = result.json()
    run = deps.agent_runs.get_agent_run(run_id=result["run_id"])
    assert run["completion_authority_required"] is True
    assert run["status"] == "planned" and run["requires_approval"] is True
    assert counts()["agent_runs"] == 1
    assert counts()["approval_effect_executions"] == counts()["approval_commands"] == 0
    assert all(
        a["status"] == "proposed"
        for a in deps.agent_actions.list_agent_actions(agent_run_id=run["id"])
    )
    recorded = counts()
    replay = confirm(client, prepared)
    assert replay.status_code == 200, replay.text
    assert replay.json()["receipt"]["replayed"] is True
    assert (
        replay.json()["receipt"]["receipt_digest"]
        == result["receipt"]["receipt_digest"]
    )
    assert counts() == recorded
    response = prepare(
        client, session_id=prepared["session_id"], message="Explain this run"
    )
    assert response.status_code == 200, response.text
    assert response.json()["state"] == "supervision"
    assert response.json()["response"]["session_id"] == prepared["session_id"]
    assert len(deps.turns.list_turns(session_id=prepared["session_id"])) == 4


@pytest.mark.parametrize(
    "fault",
    [
        "action",
        "shadow",
        "governance",
        "attempt",
        "release",
        "binding",
        "audit",
        "receipt",
    ],
)
def test_creation_fault_rolls_back_all_work(workspace_api, monkeypatch, fault):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    before = counts()

    def fail(*args, **kwargs):
        raise ValueError("injected creation failure")

    if fault == "action":
        monkeypatch.setattr(deps.agent_actions, "create_agent_action", fail)
    elif fault == "shadow":
        monkeypatch.setattr(deps.workflow_compatibility, "project_sequential_run", fail)
    elif fault == "governance":
        from api.routes.operator_workspace import _completion_coordinator
        from api.main import app

        class Broken:
            activate_run = staticmethod(fail)

        app.dependency_overrides[_completion_coordinator] = lambda: Broken()
    elif fault == "attempt":
        monkeypatch.setattr(
            "infrastructure.db.workflow.outcome_attempts.register_sequential_attempt_authority",
            fail,
        )
    elif fault == "release":
        original = deps.agent_runs.transition_agent_run_status

        def fail_release(**kwargs):
            if kwargs["status"] == "planned":
                fail()
            return original(**kwargs)

        monkeypatch.setattr(
            deps.agent_runs, "transition_agent_run_status", fail_release
        )
    elif fault == "binding":
        get_connection().execute(
            "CREATE TRIGGER fail_workspace_binding BEFORE UPDATE ON sessions BEGIN SELECT RAISE(ABORT, 'binding failure'); END"
        )
        get_connection().commit()
    elif fault == "audit":
        original = deps.agent_events.create_agent_event

        def fail_audit(**kwargs):
            if kwargs["event_type"] == "command_issued":
                fail()
            return original(**kwargs)

        monkeypatch.setattr(deps.agent_events, "create_agent_event", fail_audit)
    else:
        get_connection().execute(
            "CREATE TRIGGER fail_creation_receipt BEFORE INSERT ON operator_run_creation_receipts BEGIN SELECT RAISE(ABORT, 'receipt failure'); END"
        )
        get_connection().commit()
    if fault in {"receipt", "binding"}:
        from sqlite3 import IntegrityError

        with pytest.raises(IntegrityError, match=f"{fault} failure"):
            confirm(client, prepared)
    else:
        response = confirm(client, prepared)
        assert response.status_code == 409, response.text
    assert counts() == before
    assert not get_connection().in_transaction
    deps.users.ensure_user("later-writer")
    assert counts() == before
    assert (
        deps.operator_workspace.get_workspace(
            session_id=prepared["session_id"],
            tenant_id=TENANT,
            principal_id=f"human:{USER}",
        )["run_id"]
        is None
    )


def test_scope_drift_and_read_only_confirmation_are_blocked(workspace_api):
    client, deps = workspace_api
    exp = experiment(deps)
    prepared = prepare(client).json()
    before = counts()
    assert confirm(client, prepared, headers=_headers()).status_code == 403
    deps.experiments.update_experiment(
        experiment_id=exp["id"], client_id=TENANT, name="Changed scope"
    )
    response = confirm(client, prepared)
    assert response.status_code == 409, response.text
    assert counts() == before


def test_multiple_experiments_require_exact_selection(workspace_api):
    client, deps = workspace_api
    exp = experiment(deps, "First")
    experiment(deps, "Second")
    response = prepare(client).json()
    assert response["state"] == "clarification"
    assert "proposal" not in response
    selected = prepare(
        client, session_id=response["session_id"], experiment_id=exp["id"]
    )
    assert selected.status_code == 200, selected.text
    assert (
        selected.json()["proposal"]["preflight"]["parameters"]["experiment_id"]
        == exp["id"]
    )


def test_final_commit_failure_leaves_no_pending_work(workspace_api, monkeypatch):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    before = counts()

    class CommitFault:
        def __init__(self):
            self.conn = get_connection()

        def __getattr__(self, name):
            return getattr(self.conn, name)

        def commit(self):
            raise RuntimeError("original creation commit failure")

    monkeypatch.setattr(
        "infrastructure.db.session.operator_workspace.get_connection",
        lambda: CommitFault(),
    )
    with pytest.raises(RuntimeError, match="original creation commit failure"):
        confirm(client, prepared)
    assert not get_connection().in_transaction
    deps.users.ensure_user("unrelated-after-creation-failure")
    assert counts() == before


@pytest.mark.parametrize("race", ["role", "scope", "session", "harness"])
def test_final_lock_revalidates_authority_and_scope(workspace_api, monkeypatch, race):
    client, deps = workspace_api
    exp = experiment(deps)
    prepared = prepare(client).json()
    before = counts()
    original = deps.operator_workspace.commit_creation

    def interleave(**kwargs):
        conn = get_connection()
        if race == "role":
            conn.execute(
                "UPDATE client_users SET role='analyst' WHERE client_id=? AND user_id=?",
                (TENANT, USER),
            )
        elif race == "scope":
            conn.execute(
                "UPDATE experiments SET name='Changed after admission' WHERE id=?",
                (exp["id"],),
            )
        elif race == "session":
            conn.execute(
                "UPDATE sessions SET state_json='{}' WHERE id=?",
                (prepared["session_id"],),
            )
        else:
            from infrastructure.db.agent.agent_registry import (
                ensure_agent_registry_harness_profiles,
            )
            from application.services.agent_runtime.registry import (
                list_static_harness_profiles,
            )

            ensure_agent_registry_harness_profiles(
                profiles=list_static_harness_profiles()
            )
            conn.execute(
                "UPDATE agent_registry_harness_profiles SET allowed_run_modes_json='[\"plan_only\"]' WHERE id='conversation_supervised'"
            )
        conn.commit()
        return original(**kwargs)

    monkeypatch.setattr(deps.operator_workspace, "commit_creation", interleave)
    result = confirm(client, prepared)
    assert counts() == before
    assert result.status_code in {403, 409}, result.text


@pytest.mark.parametrize("competing", [False, True])
def test_simultaneous_confirmations_create_one_run(workspace_api, competing):
    from concurrent.futures import ThreadPoolExecutor

    client, deps = workspace_api
    experiment(deps)
    first = prepare(client).json()
    second = (
        prepare(client, session_id=first["session_id"]).json() if competing else first
    )
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(lambda proposal: confirm(client, proposal), [first, second])
        )
    assert sorted(r.status_code for r in results) == (
        [200, 409] if competing else [200, 200]
    )
    assert counts()["agent_runs"] == counts()["operator_run_creation_receipts"] == 1
    if not competing:
        assert results[0].json()["run_id"] == results[1].json()["run_id"]


@pytest.mark.parametrize(
    "change", ["scope", "principal", "tenant", "session", "digest", "expired"]
)
def test_substituted_or_expired_creation_is_blocked(workspace_api, change):
    import json
    from domain.workflow.operator_commands import canonical_digest

    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    proposal = prepared["proposal"]
    before = counts()
    if change == "digest":
        prepared["proposal"]["proposal_digest"] = "0" * 64
    else:
        conn = get_connection()
        conn.execute("DROP TRIGGER operator_creation_proposal_no_update")
        payload = {k: v for k, v in proposal.items() if k != "proposal_digest"}
        if change == "scope":
            payload["preflight"]["parameters"]["budgets"]["max_actions"] = 9999
        elif change == "expired":
            payload["expires_at"] = "2000-01-01T00:00:00+00:00"
        elif change == "principal":
            payload["principal_id"] = "human:another"
        elif change == "tenant":
            payload["tenant_id"] = "other"
        elif change == "session":
            payload["session_id"] = "another"
        digest = canonical_digest(payload)
        conn.execute(
            "UPDATE operator_run_creation_proposals SET payload_json=?,proposal_digest=? WHERE proposal_id=?",
            (json.dumps(payload), digest, proposal["proposal_id"]),
        )
        conn.commit()
        proposal["proposal_digest"] = digest
    response = confirm(client, prepared)
    assert response.status_code == 409, response.text
    assert counts() == before


def test_reload_and_new_conversation_keep_exact_bindings(workspace_api):
    client, deps = workspace_api
    experiment(deps)
    first = prepare(client).json()
    result = confirm(client, first).json()
    second = prepare(client).json()
    result2 = confirm(client, second).json()
    assert result["run_id"] != result2["run_id"]
    listing = client.get("/conversation/operator/workspaces", headers=_headers()).json()
    assert len(listing["conversations"]) == 2
    history = client.get(
        f"/conversation/operator/workspaces/{first['session_id']}", headers=_headers()
    ).json()
    assert history["run"]["id"] == result["run_id"]
    assert history["receipt"]["run_id"] == result["run_id"]
    assert history["turns"][0]["content"] == "Improve commerce performance"
    assert len(history["actions"]) == 9
    # An existing run can have a separate read conversation without changing its creation binding.
    opened = client.post(
        "/conversation/operator/workspaces/open",
        headers=_headers(),
        json={"run_id": result["run_id"]},
    )
    assert opened.status_code == 200, opened.text
    assert opened.json()["session_id"] != first["session_id"]
    assert counts()["agent_runs"] == 2


@pytest.mark.parametrize("role", ["analyst", "removed"])
def test_replay_requires_current_membership(workspace_api, role):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    assert confirm(client, prepared).status_code == 200
    conn = get_connection()
    conn.execute(
        "UPDATE client_users SET role=? WHERE client_id=? AND user_id=?",
        (role, TENANT, USER),
    )
    conn.commit()
    assert confirm(client, prepared).status_code == 403


def workspace_assertion(
    session_id,
    operation,
    *,
    proposal_id="",
    proposal_digest="",
    secret=None,
    **overrides,
):
    import base64
    import hashlib
    import hmac
    import json
    import time

    now = int(time.time())
    claims = {
        "schema_version": 1,
        "aud": "operator-run-creation-api"
        if operation == "confirm"
        else "operator-workspace-api",
        "iss": "operator-workspace-web-bff",
        "sub": USER,
        "client_id": TENANT,
        "session_id": session_id,
        "operation": operation,
        "proposal_id": proposal_id,
        "proposal_digest": proposal_digest,
        "iat": now,
        "exp": now + 30,
        "jti": "workspace-test",
    }
    claims.update(overrides)
    key = secret or (
        "operator-command-bff-test-secret-at-least-32"
        if operation == "confirm"
        else "operator-bff-test-secret-at-least-32"
    )
    encoded = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return {
        "X-Operator-Workspace-Assertion": f"{encoded}.{hmac.new(key.encode(), encoded.encode(), hashlib.sha256).hexdigest()}"
    }


def test_browser_assertions_create_only_after_exact_confirmation(workspace_api):
    client, deps = workspace_api
    experiment(deps)
    prepared = client.post(
        "/conversation/operator/workspaces/message",
        headers=workspace_assertion("new", "message"),
        json={"client_id": TENANT, "message": "Improve commerce performance"},
    )
    assert prepared.status_code == 200, prepared.text
    prepared = prepared.json()
    p = prepared["proposal"]
    headers = workspace_assertion(
        prepared["session_id"],
        "confirm",
        proposal_id=p["proposal_id"],
        proposal_digest=p["proposal_digest"],
    )
    assert confirm(client, prepared, headers=headers).status_code == 200
    assert counts()["agent_runs"] == 1


@pytest.mark.parametrize(
    "change",
    [
        "read_secret",
        "audience",
        "human",
        "tenant",
        "session",
        "proposal",
        "digest",
        "operation",
        "expired",
        "extra",
    ],
)
def test_assertion_substitution_cannot_create_a_run(workspace_api, change):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    p = prepared["proposal"]
    kwargs = {"proposal_id": p["proposal_id"], "proposal_digest": p["proposal_digest"]}
    changes = {
        "read_secret": {"secret": "operator-bff-test-secret-at-least-32"},
        "audience": {"aud": "operator-workspace-api"},
        "human": {"sub": "another-human"},
        "tenant": {"client_id": "another-tenant"},
        "session": {"session_id": "another-session"},
        "proposal": {"proposal_id": "other-proposal"},
        "digest": {"proposal_digest": "f" * 64},
        "operation": {"operation": "read"},
        "expired": {"iat": 1, "exp": 30},
        "extra": {"effect_approved": True},
    }
    kwargs.update(changes[change])
    target = kwargs.pop("session_id", prepared["session_id"])
    operation = kwargs.pop("operation", "confirm")
    response = confirm(
        client, prepared, headers=workspace_assertion(target, operation, **kwargs)
    )
    assert response.status_code in {401, 403, 404}, response.text
    assert counts()["agent_runs"] == counts()["approval_effect_executions"] == 0


def test_creation_does_not_approve_or_execute_worker_actions(
    workspace_api, monkeypatch
):
    from api.runtime_composition import default_worker

    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    receipt = confirm(client, prepared).json()["receipt"]
    calls = []

    def forbidden(**kwargs):
        calls.append(kwargs)
        pytest.fail("Creation provided execution authority without action approval")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", forbidden
    )
    result = default_worker(deps).tick_client(
        client_id=TENANT, user_id=USER, max_steps_per_run=1
    )
    assert result["steps_executed_total"] == 0 and not calls
    assert all(
        a["status"] == "proposed"
        for a in deps.agent_actions.list_agent_actions(agent_run_id=receipt["run_id"])
    )
    assert counts()["approval_effect_executions"] == 0


def test_fresh_process_replays_creation_after_run_changes(workspace_api):
    import json
    import subprocess
    import sys
    import os
    from shared.db import connection

    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    result = confirm(client, prepared).json()
    deps.agent_runs.update_agent_run(
        run_id=result["run_id"], status="paused", state="posterior_updated"
    )
    code = """
import json, sys
from pathlib import Path
from fastapi.testclient import TestClient
from api.main import app
from api.composition import default_deps
from api.utils.principals import build_agent_principal_token
from shared.config.env import get_settings
get_settings.cache_clear()
deps = default_deps()
deps.set_database_path(Path(sys.argv[1]))
deps.init_db()
principal = build_agent_principal_token(principal_id="human:operator-user", principal_type="human", client_id="operator-tenant", scopes=["agent_runs:read", "agent_runs:write"])
response = TestClient(app).post(f"/conversation/operator/workspaces/{sys.argv[2]}/proposals/{sys.argv[3]}/confirm", headers={"Authorization": f"Bearer {principal}"}, json={"proposal_digest": sys.argv[4]})
assert response.status_code == 200, response.text
print(json.dumps(response.json()))
"""
    process = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
            str(connection.DEFAULT_DB_PATH),
            prepared["session_id"],
            prepared["proposal"]["proposal_id"],
            prepared["proposal"]["proposal_digest"],
        ],
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "DATABASE_PATH": str(connection.DEFAULT_DB_PATH)},
    )
    assert process.returncode == 0, process.stderr
    replay = json.loads(process.stdout.splitlines()[-1])
    assert replay["receipt"]["replayed"] is True
    assert replay["receipt"]["receipt_digest"] == result["receipt"]["receipt_digest"]
    assert counts()["agent_runs"] == 1
    assert (
        deps.agent_runs.get_agent_run(run_id=result["run_id"])["state"]
        == "posterior_updated"
    )


def test_material_plan_drift_cannot_create_unreviewed_work(workspace_api, monkeypatch):
    from dataclasses import replace
    from application.services.agent_runtime import runs

    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    before = counts()
    original = runs.build_initial_plan

    def altered_plan(**kwargs):
        plan = original(**kwargs)
        plan[0] = replace(
            plan[0], inputs={**plan[0].inputs, "retrieval_max_results": 7}
        )
        return plan

    monkeypatch.setattr(runs, "build_initial_plan", altered_plan)
    result = confirm(client, prepared)
    assert result.status_code == 409, result.text
    assert counts() == before


def test_other_member_cannot_read_or_confirm_private_conversation(workspace_api):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    deps.users.ensure_user("other-member")
    deps.clients.add_client_user(
        client_id=TENANT, user_id="other-member", role="operator"
    )
    headers = _headers(
        principal_id="human:other-member",
        scopes=["agent_runs:read", "agent_runs:write"],
    )
    assert (
        client.get(
            f"/conversation/operator/workspaces/{prepared['session_id']}",
            headers=headers,
        ).status_code
        == 404
    )
    assert confirm(client, prepared, headers=headers).status_code == 404
    assert counts()["agent_runs"] == 0


@pytest.mark.parametrize("target", ["experiment", "product", "battery", "query"])
def test_missing_or_cross_scope_inputs_block_preparation(workspace_api, target):
    client, deps = workspace_api
    exp = experiment(deps)
    if target == "experiment":
        response = prepare(client, experiment_id="missing-experiment")
    else:
        conn = get_connection()
        if target == "product":
            deps.clients.create_client(client_id="foreign", name="Foreign tenant")
            conn.execute("UPDATE brands SET client_id='foreign' WHERE id='brand-1'")
        elif target == "battery":
            conn.execute(
                "UPDATE experiments SET battery_id=NULL WHERE id=?", (exp["id"],)
            )
        else:
            conn.execute(
                "UPDATE query_battery_queries SET enabled=0 WHERE battery_id=?",
                (exp["battery_id"],),
            )
        conn.commit()
        response = prepare(client, experiment_id=exp["id"])
    assert response.status_code in {404, 409}, response.text
    assert counts()["agent_runs"] == 0


@pytest.mark.parametrize(
    "table",
    [
        "operator_run_creation_proposals",
        "operator_run_creation_receipts",
        "operator_workspaces",
    ],
)
def test_new_decisions_and_workspace_identity_are_immutable(workspace_api, table):
    from sqlite3 import IntegrityError

    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    assert confirm(client, prepared).status_code == 200
    conn = get_connection()
    with pytest.raises(IntegrityError, match="immutable"):
        if table == "operator_workspaces":
            conn.execute("UPDATE operator_workspaces SET principal_id='human:other'")
        else:
            conn.execute(f"UPDATE {table} SET payload_json='{{}}'")
    conn.rollback()


def test_creation_projection_matches_receipt_without_approval_counts(workspace_api):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    result = confirm(client, prepared).json()
    before = counts()
    response = client.get(
        f"/conversation/operator/runs/{result['run_id']}/commands",
        headers=_headers(),
        params={"client_id": TENANT},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["creation_decision"]["receipt"] == {
        key: value for key, value in result["receipt"].items() if key != "replayed"
    }
    assert data["creation_decision"]["proposal"] == prepared["proposal"]
    assert data["records"] == [] and data["total_count"] == 0
    assert counts() == before
    assert (
        deps.operator_workspace.get_creation_for_run(
            run_id=result["run_id"], tenant_id="another-tenant"
        )
        is None
    )
