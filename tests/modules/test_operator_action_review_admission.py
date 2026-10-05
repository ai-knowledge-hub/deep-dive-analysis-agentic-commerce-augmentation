"""Fail closed when review authority or required evidence cannot be reconstructed."""

import dataclasses

import pytest

from api.main import app
from api.routes import operator_conversation
from api.runtime_composition import default_completion_coordinator
from application.services.conversation.operator_gateway import (
    OperatorConversationService,
)
from infrastructure.db.core.connection import get_connection
from tests.modules.test_operator_action_review import (
    review_api as _review_fixture,
    review_run,
    propose,
    confirm,
    assert_no_decision,
)
from test_operator_conversation_api import TENANT, USER, _bff_headers


@pytest.fixture
def review_api(tmp_path, monkeypatch):
    yield from _review_fixture.__wrapped__(tmp_path, monkeypatch)


@pytest.mark.parametrize("state", ["missing", "raises"])
def test_persistent_completion_failure_cannot_create_action_authority(
    review_api, tmp_path, state
):
    _, deps, run, action, _ = review_run(review_api, tmp_path)

    def reader(**_):
        if state == "raises":
            raise ValueError("unverifiable completion authority")
        return None

    service = OperatorConversationService(deps=deps, completion_reader=reader)
    for _ in range(2):
        result = service.respond(
            tenant_id=TENANT,
            principal_id=f"human:{USER}",
            session_user_id=USER,
            run_id=run["id"],
            message=f"Approve action {action['id']}",
        )
        assert result["command_proposal"] is None
    assert_no_decision(deps, run, action)


@pytest.mark.parametrize("change", ["registry", "completion", "validation"])
def test_evidence_change_after_early_route_read_blocks_final_commit(
    review_api, tmp_path, monkeypatch, change
):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    original = deps.operator_commands
    coordinator = default_completion_coordinator(deps)
    changed = {"active": False}
    read_completion = coordinator.get_completion_read_model
    monkeypatch.setattr(
        coordinator,
        "get_completion_read_model",
        lambda **scope: None if changed["active"] else read_completion(**scope),
    )

    class RacingStore:
        def __getattr__(self, name):
            return getattr(original, name)

        def commit_review(self, **kwargs):
            if change == "registry":
                monkeypatch.setattr(
                    "application.services.conversation.operator_action_review.registry_contract_payload",
                    lambda: {"registry_version": "changed"},
                )
            elif change == "completion":
                changed["active"] = True
            else:
                conn = get_connection()
                conn.execute(
                    'UPDATE agent_actions SET outputs_json = \'{"validation_job_id":"missing-linked-job"}\' WHERE id = ?',
                    (action["id"],),
                )
                conn.commit()
            return original.commit_review(**kwargs)

    app.dependency_overrides[operator_conversation._deps] = lambda: dataclasses.replace(
        deps, operator_commands=RacingStore()
    )
    app.dependency_overrides[operator_conversation._completion_coordinator] = lambda: (
        coordinator
    )
    result = confirm(client, run, proposal)
    assert result.status_code == 409, result.text
    assert_no_decision(deps, run, action)


def test_read_assertion_and_model_intent_cannot_authorize_review(review_api, tmp_path):
    client, deps, run, action, _ = review_run(review_api, tmp_path)
    proposal = propose(client, run, action)
    result = client.post(
        f"/conversation/operator/runs/{run['id']}/commands/{proposal['proposal_id']}/confirm",
        headers=_bff_headers(run_id=run["id"]),
        json={
            "client_id": TENANT,
            "user_id": USER,
            "command_type": "approve",
            "action_id": action["id"],
            "proposal_digest": proposal["proposal_digest"],
        },
    )
    assert result.status_code == 401
    coordinator = default_completion_coordinator(deps)
    service = OperatorConversationService(
        deps=dataclasses.replace(
            deps, generate=lambda _: '{"intent":"approve_action","fact_ids":[]}'
        ),
        completion_reader=coordinator.get_completion_read_model,
    )
    result = service.respond(
        tenant_id=TENANT,
        principal_id=f"human:{USER}",
        session_user_id=USER,
        run_id=run["id"],
        message="Explain this run",
    )
    assert result["command_proposal"] is None
    assert_no_decision(deps, run, action)
