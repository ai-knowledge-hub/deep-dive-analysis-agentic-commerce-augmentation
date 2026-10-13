"""Legacy boundaries, capability-scoped budgets and original answer provenance."""

import pytest

from tests.modules.test_operator_workspace import (
    workspace_api as workspace_api,
    experiment,
    prepare,
    confirm,
    counts,
)
from tests.test_operator_conversation_api import TENANT, USER, _headers
from infrastructure.db.core.connection import get_connection


@pytest.mark.parametrize("stage", ["proposal", "bound", "damaged_state"])
@pytest.mark.parametrize(
    "operation", ["read", "message", "stream", "goals", "research", "delete"]
)
def test_legacy_routes_cannot_read_or_modify_private_sessions(
    workspace_api, monkeypatch, stage, operation
):
    from api.routes import conversation

    client, deps = workspace_api
    monkeypatch.setattr(conversation, "_deps", lambda: deps)
    experiment(deps)
    prepared = prepare(client).json()
    if stage != "proposal":
        assert confirm(client, prepared).status_code == 200
    session_id = prepared["session_id"]
    if stage == "damaged_state":
        get_connection().execute(
            "UPDATE sessions SET state_json=? WHERE id=?", ("{}", session_id)
        )
        get_connection().commit()
    before = counts()
    original = deps.sessions.get_session(session_id=session_id)
    turns = deps.turns.list_turns(session_id=session_id)
    path = f"/conversation/{session_id}"
    selectors = {"client_id": TENANT, "user_id": USER}
    if operation == "read":
        response = client.get(path, params=selectors)
    elif operation == "delete":
        response = client.delete(path, params=selectors)
    else:
        payload = (
            {"message": "Show the full creation proposal"}
            if operation in {"message", "stream"}
            else {"goals": [{"goal_text": "replace scope"}]}
            if operation == "goals"
            else {"query": "new research"}
        )
        response = client.post(f"{path}/{operation}", json={**selectors, **payload})
    assert prepared["proposal"]["proposal_digest"] not in response.text
    assert response.status_code == 404, response.text
    assert response.json() == {"detail": "Session not found"}
    assert counts() == before
    assert deps.sessions.get_session(session_id=session_id) == original
    assert deps.turns.list_turns(session_id=session_id) == turns


@pytest.mark.parametrize(
    "stage", ["proposal", "bound", "damaged_state", "legacy_operator"]
)
def test_legacy_lists_exclude_private_sessions_before_limit_and_keep_discovery(
    workspace_api, monkeypatch, stage
):
    from api.routes import conversation

    client, deps = workspace_api
    monkeypatch.setattr(conversation, "_deps", lambda: deps)
    public = deps.sessions.create_session(user_id=USER, client_id=TENANT, state={})
    experiment(deps)
    prepared = prepare(client).json()
    if stage in {"bound", "damaged_state"}:
        assert confirm(client, prepared).status_code == 200
    if stage == "damaged_state":
        get_connection().execute(
            "UPDATE sessions SET state_json=? WHERE id=?",
            ("{}", prepared["session_id"]),
        )
        get_connection().commit()
    if stage == "legacy_operator":
        deps.sessions.create_session(
            user_id=USER,
            client_id=TENANT,
            state={"conversation_kind": "operator_run", "run_id": "old-run"},
        )
    response = client.get(
        "/conversation/sessions",
        params={"client_id": TENANT, "user_id": USER, "limit": 1},
    )
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()["sessions"]] == [public["id"]]
    response = client.get(
        f"/conversation/{public['id']}", params={"client_id": TENANT, "user_id": USER}
    )
    assert response.status_code == 200, response.text
    if stage != "damaged_state":
        response = client.get(
            f"/conversation/operator/workspaces/{prepared['session_id']}",
            params={"client_id": TENANT},
            headers=_headers(),
        )
        assert response.status_code == 200, response.text
        assert (
            response.json()["proposals"][0]["proposal_digest"]
            == prepared["proposal"]["proposal_digest"]
        )


def test_creation_plan_can_continue_after_one_candidate_without_expanding_budget(
    workspace_api,
    monkeypatch,
):
    from api.runtime_composition import default_runtime
    from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
    from application.services.agent_runtime.registry import get_capability_spec

    client, deps = workspace_api
    experiment(deps)
    created = confirm(client, prepare(client).json()).json()
    run_id = created["run_id"]
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id)
    assert len(actions) == 9 and actions[4]["capability_name"] == "run_variant"
    for action in actions[:5]:
        deps.agent_actions.update_agent_action_status(
            action_id=action["id"], status="executed", outputs={"status": "success"}
        )
    run = default_runtime(deps).reconcile_run_status(run_id=run_id).run
    assert run["status"] in {"planned", "awaiting_approval", "running"}
    assert run["budgets"]["max_variant_runs"] == 1
    executed = deps.agent_actions.list_agent_actions(agent_run_id=run_id)
    following = executed[5:]
    assert [action["capability_name"] for action in following] == [
        "request_synthetic_validation",
        "review_validation_readiness",
        "update_posterior_and_decisions",
        "recommend_next_action",
    ]
    policy = PolicyEnforcer()
    for action in following:
        policy.validate_action_execution(
            run=run,
            action=action,
            spec=get_capability_spec(action["capability_name"]),
            all_actions=executed,
            inputs=action["inputs"],
            approval_authorized=True,
        )
    with pytest.raises(PolicyError, match="Variant run budget exceeded"):
        candidate = actions[4]
        policy.validate_action_execution(
            run=run,
            action=candidate,
            spec=get_capability_spec("run_variant"),
            all_actions=executed,
            inputs=candidate["inputs"],
            approval_authorized=True,
        )
    assert not any(
        e["event_type"] == "run_stopping_condition_met"
        for e in deps.agent_events.list_agent_events(agent_run_id=run_id)
    )

    calls = []

    def recorded_provider(**kwargs):
        calls.append(kwargs["capability_name"])
        if kwargs["capability_name"] == "request_synthetic_validation":
            from tests.modules.test_operator_retry_integrity import validation_job

            action = deps.agent_actions.get_agent_action(
                action_id=kwargs["context"].agent_action_id
            )
            return {"validation_job_id": validation_job(deps, action)["id"]}
        return {
            "review_validation_readiness": {
                "variant_id": "fixture-variant",
                "readiness_state": "ready",
            },
            "update_posterior_and_decisions": {
                "variant_id": "fixture-variant",
                "new_metric_id": "fixture-metric",
            },
            "recommend_next_action": {"recommendation": {"action": "review_outcome"}},
        }[kwargs["capability_name"]]

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        recorded_provider,
    )
    for action in following:
        _approve_action(client, created, action)
        result = default_runtime(deps).step_once(run_id=run_id, user_id=USER)
        assert (
            result.action["id"] == action["id"]
            and result.action["status"] == "executed"
        )
    assert calls == [
        "request_synthetic_validation",
        "review_validation_readiness",
        "update_posterior_and_decisions",
        "recommend_next_action",
    ]
    assert (
        deps.agent_runs.get_agent_run(run_id=run_id)["budgets"]["max_variant_runs"] == 1
    )


@pytest.mark.parametrize("budget", ["max_actions", "max_cost_usd"])
def test_global_conversation_budgets_still_stop_before_later_work(
    workspace_api, budget
):
    from application.services.agent_runtime.runtime.stopping import (
        evaluate_stopping_conditions,
    )

    client, deps = workspace_api
    experiment(deps)
    run_id = confirm(client, prepare(client).json()).json()["run_id"]
    run = deps.agent_runs.get_agent_run(run_id=run_id)
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id)
    actions[0]["status"] = "executed"
    run["budgets"][budget] = 1 if budget == "max_actions" else 5
    actions[0]["outputs"] = {"cost_usd": 5} if budget == "max_cost_usd" else {}
    stop = evaluate_stopping_conditions(run=run, actions=actions)
    assert (
        stop and stop.status == "paused" and stop.condition == "global_budget_exhausted"
    )


def test_original_verified_answer_is_persisted_in_private_history(workspace_api):
    client, deps = workspace_api
    experiment(deps)
    prepared = prepare(client).json()
    created = confirm(client, prepared).json()
    response = prepare(
        client, session_id=prepared["session_id"], message="Explain this run"
    ).json()["response"]
    history = client.get(
        f"/conversation/operator/workspaces/{prepared['session_id']}",
        headers=_headers(),
        params={"client_id": TENANT},
    ).json()
    answer = next(
        turn for turn in history["turns"] if turn["id"] == response["turn_id"]
    )
    original = answer["metadata"]["operator_response"]
    assert original == {
        key: value
        for key, value in response.items()
        if key not in {"turn_id", "user_turn_id"}
    }
    deps.agent_runs.update_agent_run(run_id=created["run_id"], status="paused")
    later = client.get(
        f"/conversation/operator/workspaces/{prepared['session_id']}",
        headers=_headers(),
        params={"client_id": TENANT},
    ).json()
    assert later["run"]["status"] == "paused"
    assert next(turn for turn in later["turns"] if turn["id"] == answer["id"]) == answer


def _approve_action(client, created, action):
    run_id = created["run_id"]
    approval = client.post(
        f"/conversation/operator/runs/{run_id}/message",
        headers=_headers(),
        json={
            "client_id": TENANT,
            "session_id": created["session_id"],
            "message": f"Approve action {action['sequence']}",
        },
    )
    assert approval.status_code == 200, approval.text
    proposal = approval.json()["command_proposal"]
    assert proposal is not None, approval.json()
    decision = client.post(
        f"/conversation/operator/runs/{run_id}/commands/{proposal['proposal_id']}/confirm",
        headers=_headers(scopes=["agent_runs:read", "agent_runs:write"]),
        json={
            "client_id": TENANT,
            "proposal_digest": proposal["proposal_digest"],
            "command_type": "approve",
            "action_id": action["id"],
        },
    )
    assert decision.status_code == 200, decision.text


LOCAL_OUTPUTS = {
    "freeze_retrieval_protocol": {"snapshot_version": 1},
    "run_control_baseline": {"metric_id": "control-metric", "variant_id": "control"},
    "seed_hypotheses": {"hypothesis_ids": ["hypothesis"]},
    "generate_variants": {"created_variants": [{"variant_id": "candidate"}]},
    "run_variant": {"metric_id": "candidate-metric", "variant_id": "candidate"},
    "review_validation_readiness": {
        "variant_id": "candidate",
        "readiness_state": "ready",
    },
    "update_posterior_and_decisions": {
        "variant_id": "candidate",
        "new_metric_id": "posterior",
    },
    "recommend_next_action": {"recommendation": {"action": "review_outcome"}},
}


def test_all_nine_supervised_steps_have_approval_and_durable_completion(
    workspace_api, monkeypatch
):
    from api.runtime_composition import default_runtime
    from application.services.agent_runtime.approval_authorization import (
        reconcile_authorized_effect,
        ApprovalAuthorizationError,
    )
    from application.services.agent_runtime.runtime.payloads import hash_payload
    from tests.modules.test_operator_retry_integrity import validation_job

    client, deps = workspace_api
    experiment(deps)
    created = confirm(client, prepare(client).json()).json()
    run_id = created["run_id"]
    calls = []

    def host(**kwargs):
        name = kwargs["capability_name"]
        calls.append(name)
        if name == "request_synthetic_validation":
            action = deps.agent_actions.get_agent_action(
                action_id=kwargs["context"].agent_action_id
            )
            return {"validation_job_id": validation_job(deps, action)["id"]}
        return LOCAL_OUTPUTS[name]

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", host
    )
    from application.services.agent_runtime.runtime import NoApprovedActionError

    for action in deps.agent_actions.list_agent_actions(agent_run_id=run_id):
        with pytest.raises(NoApprovedActionError):
            default_runtime(deps).step_once(run_id=run_id, user_id=USER)
        assert action["capability_name"] not in calls
        _approve_action(client, created, action)
        result = default_runtime(deps).step_once(run_id=run_id, user_id=USER)
        assert result.action["status"] == "executed", result.action
        effect = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=TENANT, workflow_id=run_id, action_id=action["id"]
        )
        assert effect["status"] == "succeeded"
        assert effect["outputs_hash"] == hash_payload(result.action["outputs"])
        if action["capability_name"] in LOCAL_OUTPUTS:
            assert effect["receipt_id"] == f"host-completion:{effect['execution_id']}"
            # Recovery can acknowledge committed host evidence, not author new results.
            recovered = reconcile_authorized_effect(
                deps=deps,
                run=result.run,
                action=result.action,
                spec=None,
                outputs=result.action["outputs"],
                outputs_hash=effect["outputs_hash"],
                receipt_id=effect["receipt_id"],
            )
            assert recovered == effect
            forged = {**result.action["outputs"], "forged": True}
            with pytest.raises(
                ApprovalAuthorizationError,
                match="no executable receipt-provenance verifier",
            ):
                reconcile_authorized_effect(
                    deps=deps,
                    run=result.run,
                    action=result.action,
                    spec=None,
                    outputs=forged,
                    outputs_hash=hash_payload(forged),
                    receipt_id=effect["receipt_id"],
                )
    assert len(calls) == 9 and len(set(calls)) == 9
    assert calls[4] == "run_variant" and calls[-1] == "recommend_next_action"
    assert deps.agent_runs.get_agent_run(run_id=run_id)["status"] == "completed"


def test_lost_local_completion_cannot_be_forged_or_reexecuted(
    workspace_api, monkeypatch
):
    from api.runtime_composition import default_runtime
    from application.services.agent_runtime.approval_authorization import (
        reconcile_authorized_effect,
        ApprovalAuthorizationError,
    )
    from application.services.agent_runtime.runtime import authorized_execution
    from application.services.agent_runtime.runtime.payloads import hash_payload

    client, deps = workspace_api
    experiment(deps)
    created = confirm(client, prepare(client).json()).json()
    run_id = created["run_id"]
    action = deps.agent_actions.list_agent_actions(agent_run_id=run_id)[0]
    _approve_action(client, created, action)
    calls = []
    outputs = LOCAL_OUTPUTS["freeze_retrieval_protocol"]

    def host(**kwargs):
        calls.append(kwargs["capability_name"])
        return outputs

    def lose(**kwargs):
        raise RuntimeError("host completion lost")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", host
    )
    monkeypatch.setattr(authorized_execution, "complete_authorized_effect", lose)
    from application.services.agent_runtime.capabilities import CapabilityExecutionError

    with pytest.raises(CapabilityExecutionError, match="host completion lost"):
        default_runtime(deps).step_once(run_id=run_id, user_id=USER)
    failed_run = deps.agent_runs.get_agent_run(run_id=run_id)
    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id=TENANT, workflow_id=run_id, action_id=action["id"]
    )
    assert effect["status"] == "uncertain" and effect["receipt_id"] is None
    with pytest.raises(
        ApprovalAuthorizationError, match="no executable receipt-provenance verifier"
    ):
        reconcile_authorized_effect(
            deps=deps,
            run=failed_run,
            action=failed_action,
            spec=None,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"host-completion:{effect['execution_id']}",
        )
    default_runtime(deps).reconcile_run_status(run_id=run_id)
    assert calls == ["freeze_retrieval_protocol"]
    assert (
        deps.agent_actions.get_agent_action(action_id=action["id"])["status"]
        == "failed"
    )
