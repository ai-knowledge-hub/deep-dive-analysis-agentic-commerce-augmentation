"""Queued sibling retries cannot consume a second governed provider effect."""

import pytest
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from api.runtime_composition import default_worker
from infrastructure.db.core.connection import get_connection
from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    commit_pre_effect_authorization,
    mark_authorized_effect_uncertain,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from tests.modules.test_approval_effect_authorization import (
    _execution_lease,
    _run_and_action,
    _additional_action,
    _approve,
)
from tests.modules.test_operator_retry import (
    retry_api as _fixture,
    source,
    propose,
    confirm,
)
from tests.modules.test_operator_retry_integrity import validation_job
from tests.modules.test_operator_action_review import (
    propose as propose_review,
    confirm as confirm_review,
)
from test_operator_conversation_api import TENANT, USER


@pytest.fixture
def retry_api(tmp_path, monkeypatch):
    yield from _fixture.__wrapped__(tmp_path, monkeypatch)


def approved_siblings(retry_api, tmp_path, *, rewritten=False):
    client, deps, run, source_action, spec = source(retry_api, tmp_path)
    siblings = []
    for _ in range(2):
        receipt = confirm(client, run, propose(client, run, source_action)).json()[
            "receipt"
        ]
        child = deps.agent_actions.get_agent_action(action_id=receipt["action_id"])
        if rewritten:
            conn = get_connection()
            conn.execute(
                "UPDATE agent_actions SET dedupe_key = ? WHERE id = ?",
                (f"replacement:{child['id']}", child["id"]),
            )
            conn.commit()
            child = deps.agent_actions.get_agent_action(action_id=child["id"])
        review = propose_review(client, run, child)
        assert confirm_review(client, run, review).status_code == 200
        siblings.append(deps.agent_actions.get_agent_action(action_id=child["id"]))
    return client, deps, run, source_action, siblings, spec


def executing(deps, action):
    return deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )


def start(deps, run, action, spec, token):
    return commit_pre_effect_authorization(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        executable_inputs=action["inputs"],
        lock_token=token,
    )


def assert_one_start(deps, run, winner, loser, *, tenant=TENANT):
    conn = get_connection()
    effects = conn.execute(
        "SELECT action_id FROM approval_effect_executions WHERE workflow_id = ?",
        (run["id"],),
    ).fetchall()
    assert [row["action_id"] for row in effects] == [winner["id"]]
    audits = conn.execute(
        "SELECT action_id FROM agent_events WHERE agent_run_id = ? AND event_type = 'approval_effect_started'",
        (run["id"],),
    ).fetchall()
    assert [row["action_id"] for row in audits] == [winner["id"]]
    approval = deps.approval_ledger.get_approval(
        tenant_id=tenant, workflow_id=run["id"], approval_id=loser["approval_id"]
    )
    assert approval["status"] == "approved"


@pytest.mark.parametrize("state", ["started", "uncertain", "succeeded"])
@pytest.mark.parametrize("winner_index", [0, 1])
@pytest.mark.parametrize("rewritten", [False, True])
def test_prequeued_sibling_states_and_immutable_relationships(
    retry_api, tmp_path, state, winner_index, rewritten
):
    _, deps, run, _, siblings, spec = approved_siblings(
        retry_api, tmp_path, rewritten=rewritten
    )
    actions = [executing(deps, child) for child in siblings]
    run, token = _execution_lease(deps, run)
    winner, loser = actions[winner_index], actions[1 - winner_index]
    auth = start(deps, run, winner, spec, token)
    if state == "uncertain":
        mark_authorized_effect_uncertain(
            deps=deps,
            run=run,
            action=winner,
            authorization=auth,
            error_code="provider_timeout",
        )
    elif state == "succeeded":
        job = validation_job(deps, winner)
        outputs = {"validation_job_id": job["id"]}
        reconcile_authorized_effect(
            deps=deps,
            run=run,
            action=winner,
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{job['id']}",
        )
    with pytest.raises(ApprovalAuthorizationError) as exc:
        start(deps, run, loser, spec, token)
    assert exc.value.code == "retry_family_effect_already_started"
    assert_one_start(deps, run, winner, loser)
    if state != "succeeded":
        with pytest.raises(ApprovalAuthorizationError) as replay:
            start(deps, run, winner, spec, token)
        assert replay.value.code == "effect_reconciliation_required"


def test_sibling_commit_after_validation_is_seen_at_final_lock(
    retry_api, tmp_path, monkeypatch
):
    _, deps, run, _, siblings, spec = approved_siblings(retry_api, tmp_path)
    winner, loser = [executing(deps, child) for child in siblings]
    run, token = _execution_lease(deps, run)
    original = deps.approval_ledger.commit_effect_authorization

    def commit_after_validation(**kwargs):
        # Both approvals were admitted before either effect. Commit the winner
        # after the loser's application validation, before its DB transaction.
        monkeypatch.setattr(
            deps.approval_ledger, "commit_effect_authorization", original
        )
        start(deps, run, winner, spec, token)
        return original(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_effect_authorization", commit_after_validation
    )
    with pytest.raises(ApprovalAuthorizationError) as exc:
        start(deps, run, loser, spec, token)
    assert exc.value.code == "retry_family_effect_already_started"
    assert_one_start(deps, run, winner, loser)


def test_simultaneous_sibling_starts_reserve_one_effect(
    retry_api, tmp_path, monkeypatch
):
    _, deps, run, _, siblings, spec = approved_siblings(retry_api, tmp_path)
    actions = [executing(deps, child) for child in siblings]
    run, token = _execution_lease(deps, run)
    barrier = Barrier(2)
    original = deps.approval_ledger.commit_effect_authorization

    def synchronized_commit(**kwargs):
        barrier.wait(timeout=10)
        return original(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_effect_authorization", synchronized_commit
    )

    def contender(action):
        try:
            start(deps, run, action, spec, token)
            return "started"
        except ApprovalAuthorizationError as exc:
            return exc.code
        finally:
            get_connection().close()

    # Share one valid lease deliberately to isolate the DB arbiter even when
    # duplicate dispatch happens inside the lease-owning worker.
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(contender, actions))
    assert sorted(outcomes) == ["retry_family_effect_already_started", "started"]
    winner_index = outcomes.index("started")
    assert_one_start(deps, run, actions[winner_index], actions[1 - winner_index])


@pytest.mark.parametrize("related", [False, True])
def test_legacy_family_is_fenced_but_independent_identical_inputs_are_allowed(
    tmp_path, related
):
    deps, run, source_action, spec = _run_and_action(tmp_path)
    children = []
    for index in range(2):
        child = _additional_action(
            deps,
            run,
            spec,
            sequence=index + 2,
            dedupe_key=f"retry:{source_action['id']}:same_action:{index + 1}"
            if related
            else f"independent:{index}",
        )
        conn = get_connection()
        conn.execute(
            "UPDATE agent_actions SET inputs_json = ? WHERE id = ?",
            ('{"experiment_id":"identical"}', child["id"]),
        )
        conn.commit()
        child = deps.agent_actions.get_agent_action(action_id=child["id"])
        children.append(executing(deps, _approve(deps, run, child)["action"]))
    assert children[0]["inputs_hash"] == children[1]["inputs_hash"]
    run, token = _execution_lease(deps, run)
    start(deps, run, children[0], spec, token)
    if related:
        with pytest.raises(ApprovalAuthorizationError) as exc:
            start(deps, run, children[1], spec, token)
        assert exc.value.code == "retry_family_effect_already_started"
        assert_one_start(deps, run, *children, tenant="client-a")
    else:
        start(deps, run, children[1], spec, token)
        assert (
            get_connection()
            .execute(
                "SELECT COUNT(*) FROM approval_effect_executions WHERE workflow_id = ?",
                (run["id"],),
            )
            .fetchone()[0]
            == 2
        )


def test_preapproved_siblings_worker_invokes_provider_once(
    retry_api, tmp_path, monkeypatch
):
    _, deps, run, source_action, siblings, _ = approved_siblings(retry_api, tmp_path)
    calls = []

    def execute_capability(*, context, **_):
        child = deps.agent_actions.get_agent_action(action_id=context.agent_action_id)
        calls.append(child["id"])
        job = validation_job(deps, child)
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
    worker = default_worker(deps)
    worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=2)
    worker.tick_client(client_id=TENANT, user_id=USER, max_steps_per_run=2)
    assert calls == [siblings[0]["id"]]
    effects = (
        get_connection()
        .execute(
            "SELECT action_id, status FROM approval_effect_executions WHERE workflow_id = ?",
            (run["id"],),
        )
        .fetchall()
    )
    assert [(row["action_id"], row["status"]) for row in effects] == [
        (siblings[0]["id"], "succeeded")
    ]
    blocked = deps.agent_actions.get_agent_action(action_id=siblings[1]["id"])
    assert blocked["status"] == "failed" and "retry" in blocked["error"].lower()
    assert (
        deps.agent_actions.get_agent_action(action_id=source_action["id"])
        == source_action
    )
