"""Independent authority and projection boundaries for historical reconciliation."""

import dataclasses
import json

import pytest

from api.main import app
from api.routes import operator_conversation
from domain.workflow.operator_commands import canonical_digest
from infrastructure.db.agent.operator_reconciliations import (
    verify_reconciliation_receipt,
)
from infrastructure.db.core.connection import get_connection
from tests.modules.test_operator_reconciliation import (
    reconciliation_api as _fixture,
    source,
    propose,
    confirm,
    assert_unrecorded,
)
from test_operator_conversation_api import TENANT, USER, _post, _headers, _action


@pytest.fixture
def reconciliation_api(tmp_path, monkeypatch):
    yield from _fixture.__wrapped__(tmp_path, monkeypatch)


def test_model_cannot_choose_reconciliation_authority(reconciliation_api, tmp_path):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    injected = dataclasses.replace(
        deps,
        generate=lambda _: json.dumps(
            {
                "intent": "reconcile_effect",
                "action_id": action["id"],
                "outputs": {"status": "succeeded"},
                "fact_ids": [],
            }
        ),
    )
    app.dependency_overrides[operator_conversation._deps] = lambda: injected
    response = _post(client, run["id"], message="Explain the last outcome")
    assert response.status_code == 200
    assert response.json()["command_proposal"] is None
    assert (
        get_connection()
        .execute("SELECT count(*) FROM operator_reconciliation_proposals")
        .fetchone()[0]
        == 0
    )
    assert_unrecorded(deps, run, action)


def test_unverifiable_completion_blocks_recording_after_proposal(
    reconciliation_api, tmp_path
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)

    class Broken:
        def get_completion_read_model(self, **_):
            raise ValueError("corrupt authority")

    app.dependency_overrides[operator_conversation._completion_coordinator] = Broken
    assert confirm(client, run, proposal).status_code == 409
    assert_unrecorded(deps, run, action)


@pytest.mark.parametrize(
    "scope,expected",
    [
        ("agent_runs:read", 403),
        ("operator_commands:confirm", 403),
        ("operator_action_reviews:confirm", 403),
        ("operator_retries:confirm", 403),
        ("operator_reconciliations:confirm", 200),
        ("agent_runs:write", 200),
    ],
)
def test_direct_human_authority_is_command_scoped(
    reconciliation_api, tmp_path, scope, expected
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    proposal = propose(client, run, action)
    response = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_headers(scopes=[scope]),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "command_type": "reconcile_effect",
            "proposal_digest": proposal["proposal_digest"],
            "action_id": action["id"],
            "effect_execution_id": proposal["parameters"]["effect_execution_id"],
        },
    )
    assert response.status_code == expected, response.text
    if expected == 403:
        assert_unrecorded(deps, run, action)


def test_recording_one_outcome_does_not_resolve_unrelated_failure(
    reconciliation_api, tmp_path
):
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    get_connection().execute(
        "UPDATE agent_actions SET sequence = 2 WHERE id = ?", (action["id"],)
    )
    get_connection().commit()
    other = _action(deps, run["id"])
    deps.agent_actions.update_agent_action_status(
        action_id=other["id"], status="failed", error="unrelated failure"
    )
    response = confirm(client, run, propose(client, run, action))
    assert response.status_code == 200, response.text
    assert response.json()["receipt"]["resulting_run_status"] == "failed"
    assert (
        deps.agent_actions.get_agent_action(action_id=other["id"])["status"] == "failed"
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("extra", True),
        ("prior_run_state", "invented"),
        ("request_hash", "1" * 64),
        ("control_state_preserved", False),
        ("run_mode", "dry_run"),
        ("active_graph_revision", 2),
        ("acknowledgement", "objective_completed"),
        ("propagation_state", "all_effects_certified"),
        ("resulting_run_status", "planned"),
        (
            "event_ids",
            {"command": "other", "lifecycle": "other", "stopping_condition": "cleared"},
        ),
    ],
)
def test_coordinated_receipt_rewrite_cannot_invent_control_outcome(
    reconciliation_api, tmp_path, field, value
):
    client, _, run, action, _ = source(reconciliation_api, tmp_path, status="canceled")
    assert confirm(client, run, propose(client, run, action)).status_code == 200
    row = dict(
        get_connection()
        .execute("SELECT * FROM operator_reconciliation_receipts")
        .fetchone()
    )
    receipt = json.loads(row["receipt_json"])
    receipt[field] = value
    receipt.pop("receipt_digest")
    receipt["receipt_digest"] = canonical_digest(receipt)
    row["receipt_json"], row["receipt_digest"] = (
        json.dumps(receipt),
        receipt["receipt_digest"],
    )
    if field in row:
        row[field] = value
    with pytest.raises(ValueError):
        verify_reconciliation_receipt(row)


@pytest.mark.parametrize(
    "effect_status,action_status",
    [
        ("started", "failed"),
        ("uncertain", "executing"),
        ("succeeded", "executed"),
    ],
)
def test_supported_historical_effect_projection_pairs(
    reconciliation_api, tmp_path, monkeypatch, effect_status, action_status
):
    if effect_status == "started":
        monkeypatch.setattr(
            "tests.modules.test_operator_reconciliation.mark_authorized_effect_uncertain",
            lambda **_: None,
        )
    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    if effect_status == "succeeded":
        from application.services.agent_runtime.effect_recovery import (
            reconcile_effect_from_durable_evidence,
        )

        reconcile_effect_from_durable_evidence(
            deps=deps, run=run, action=action, infer_legacy_completion=False
        )
        run = deps.agent_runs.get_agent_run(run_id=run["id"])
    else:
        deps.agent_actions.update_agent_action_status(
            action_id=action["id"], status=action_status
        )
    response = confirm(client, run, propose(client, run, action))
    assert response.status_code == 200, response.text
    assert (
        response.json()["receipt"]["reconciliation"]["effect_status"] == effect_status
    )
    assert response.json()["run"]["status"] == "planned"
    assert (
        get_connection()
        .execute("SELECT count(*) FROM approval_effect_executions")
        .fetchone()[0]
        == 1
    )
    assert (
        get_connection()
        .execute("SELECT count(*) FROM approval_commands WHERE command_type='fulfill'")
        .fetchone()[0]
        == 1
    )


@pytest.mark.parametrize("status", ["planned", "running", "failed"])
def test_acknowledging_historical_success_preserves_later_progress(
    reconciliation_api, tmp_path, monkeypatch, status
):
    from application.services.agent_runtime.effect_recovery import (
        reconcile_effect_from_durable_evidence,
    )

    client, deps, run, action, _ = source(reconciliation_api, tmp_path)
    recovered = reconcile_effect_from_durable_evidence(
        deps=deps, run=run, action=action, infer_legacy_completion=False
    )
    assert recovered["run"]["state"] == "validation_completed"
    later = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="executed",
        capability_name="update_posterior_and_decisions",
        capability_version="1",
        inputs={},
        outputs={"status": "posterior_updated"},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Later posterior update",
        confidence=1.0,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    progressed = deps.agent_runs.update_agent_run(
        run_id=run["id"],
        state="posterior_updated",
        status=status,
        error="Current run diagnostic",
    )
    conn = get_connection()
    effects_before = [
        tuple(row) for row in conn.execute("SELECT * FROM approval_effect_executions")
    ]
    fulfillments_before = conn.execute(
        "SELECT count(*) FROM approval_commands WHERE command_type='fulfill'"
    ).fetchone()[0]

    def forbidden(**_):
        pytest.fail("Acknowledging existing success attempted a run projection write")

    # Check the actual durable state before replay, independently of receipt wording.
    proposal = propose(client, progressed, recovered["action"])
    response = confirm(client, progressed, proposal)
    assert response.status_code == 200, response.text
    current = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert current == progressed
    assert current["state"] == "posterior_updated" and current["status"] == status
    receipt = response.json()["receipt"]
    assert (
        receipt["prior_run_state"]
        == receipt["resulting_run_state"]
        == "posterior_updated"
    )
    assert receipt["prior_run_status"] == receipt["resulting_run_status"] == status
    assert receipt["control_state_preserved"] is True
    assert deps.agent_actions.get_agent_action(action_id=later["id"]) == later
    assert [
        tuple(row) for row in conn.execute("SELECT * FROM approval_effect_executions")
    ] == effects_before
    assert (
        conn.execute(
            "SELECT count(*) FROM approval_commands WHERE command_type='fulfill'"
        ).fetchone()[0]
        == fulfillments_before
        == 1
    )

    monkeypatch.setattr(
        deps.agent_runs, "restore_agent_run_after_effect_reconciliation", forbidden
    )
    replay = confirm(client, progressed, proposal)
    assert replay.status_code == 200 and replay.json()["receipt"]["replayed"]
    assert replay.json()["receipt"]["receipt_digest"] == receipt["receipt_digest"]
    assert deps.agent_runs.get_agent_run(run_id=run["id"]) == progressed
