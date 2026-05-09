from __future__ import annotations

import sys
import types
import base64
import hashlib
import hmac
import json
import time

import pytest
from fastapi.testclient import TestClient

if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")
    genai_pkg.Client = lambda *args, **kwargs: None
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from api.composition import default_deps
from api.main import app
from api.utils.principals import build_agent_principal_token
from infrastructure.db.agent.external_agent_jobs import (
    create_external_agent_job,
    create_external_agent_job_receipt,
    get_external_agent_job_by_idempotency_key,
)
from shared.config.env import get_settings
from shared.db.connection import init_db, set_database_path

CLIENT_ID = "client-a"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    get_settings.cache_clear()
    db_path = tmp_path / "external-agent-jobs-api.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=CLIENT_ID, name="Client A")
    deps.clients.create_client(client_id="client-b", name="Client B")
    return TestClient(app)


def _token(*, principal_id: str = "agent-ext-1", client_id: str = CLIENT_ID, scopes=None):
    return build_agent_principal_token(
        principal_id=principal_id,
        client_id=client_id,
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=scopes or [
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:experiment.run_variant",
            "skill:optimize-product-representation",
        ],
    )


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_external_agent_job_create_is_idempotent_and_status_is_scoped(
    client: TestClient,
):
    token = _token()
    payload = {
        "idempotency_key": "job-123",
        "tool_id": "experiment.run_variant",
        "objective": {"goal": "test one variant"},
    }

    first = client.post(
        "/external-agent/jobs", headers=_headers(token), json=payload
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["idempotent_replay"] is False
    assert first_payload["job"]["status"] == "accepted"
    assert first_payload["job"]["requested_tool_id"] == "experiment.run_variant"
    assert first_payload["job"]["requested_skill_id"] == "optimize-product-representation"
    assert first_payload["job"]["trace_id"].startswith("trace_")
    assert first_payload["run"]["principal_type"] == "external_agent"
    assert first_payload["run"]["principal_id"] == "agent-ext-1"
    assert first_payload["run"]["idempotency_key"] == "job-123"
    assert first_payload["run"]["allowed_capabilities"] == ["run_variant"]

    second = client.post(
        "/external-agent/jobs", headers=_headers(token), json=payload
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["idempotent_replay"] is True
    assert second_payload["job"]["id"] == first_payload["job"]["id"]
    assert second_payload["run"]["id"] == first_payload["run"]["id"]

    status = client.get(
        f"/external-agent/jobs/{first_payload['job']['id']}",
        headers=_headers(token),
    )
    assert status.status_code == 200
    assert status.json()["job"]["id"] == first_payload["job"]["id"]

    other_principal_token = _token(principal_id="agent-ext-2")
    wrong_principal = client.get(
        f"/external-agent/jobs/{first_payload['job']['id']}",
        headers=_headers(other_principal_token),
    )
    assert wrong_principal.status_code == 404


def test_external_agent_job_single_tool_plan_ignores_extra_capabilities(
    client: TestClient,
):
    token = _token(
        scopes=[
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:experiment.run_variant",
            "tool:hypothesis.seed",
            "skill:optimize-product-representation",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-single-tool-plan",
            "tool_id": "experiment.run_variant",
            "allowed_capabilities": ["seed_hypotheses"],
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["run"]["allowed_capabilities"] == ["run_variant"]
    assert payload["run"]["objective"]["plan_mode"] == "single_tool"

    deps = default_deps()
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=payload["run"]["id"], limit=10
    )
    assert [action["capability_name"] for action in actions] == ["run_variant"]


def test_external_agent_job_workflow_plan_allows_multiple_capabilities(
    client: TestClient,
):
    token = _token(
        scopes=[
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:experiment.run_variant",
            "tool:hypothesis.seed",
            "skill:optimize-product-representation",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-workflow-plan",
            "tool_id": "experiment.run_variant",
            "allowed_capabilities": ["seed_hypotheses"],
            "plan_mode": "workflow",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["run"]["allowed_capabilities"] == [
        "run_variant",
        "seed_hypotheses",
    ]
    assert payload["run"]["objective"]["plan_mode"] == "workflow"

    deps = default_deps()
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=payload["run"]["id"], limit=10
    )
    assert [action["capability_name"] for action in actions] == [
        "seed_hypotheses",
        "run_variant",
    ]


def test_external_agent_job_action_uses_requested_skill_lineage(
    client: TestClient,
):
    token = _token(
        scopes=[
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:validation.review_readiness",
            "skill:promote-and-publish-approved-copy",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-preferred-skill",
            "tool_id": "validation.review_readiness",
            "skill_id": "promote-and-publish-approved-copy",
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["job"]["requested_skill_id"] == "promote-and-publish-approved-copy"

    deps = default_deps()
    actions = deps.agent_actions.list_agent_actions(
        agent_run_id=payload["run"]["id"], limit=10
    )
    assert len(actions) == 1
    assert actions[0]["tool_id"] == "validation.review_readiness"
    assert actions[0]["skill_id"] == "promote-and-publish-approved-copy"


def test_external_agent_job_rejects_unknown_profiles(client: TestClient):
    token = _token()
    base = {
        "idempotency_key": "job-bad-runtime-profile",
        "tool_id": "experiment.run_variant",
    }
    bad_run_mode = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={**base, "run_mode": "manual"},
    )
    assert bad_run_mode.status_code == 400
    assert "Unsupported run_mode: manual" in bad_run_mode.json()["detail"]

    bad_policy = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={**base, "idempotency_key": "job-bad-policy", "policy_profile_id": "unknown"},
    )
    assert bad_policy.status_code == 400
    assert "Unsupported policy_profile_id: unknown" in bad_policy.json()["detail"]

    bad_harness = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={**base, "idempotency_key": "job-bad-harness", "harness_id": "pretend"},
    )
    assert bad_harness.status_code == 400
    assert "Unsupported harness_id: pretend" in bad_harness.json()["detail"]


def test_external_agent_job_rejects_idempotency_payload_mismatch(client: TestClient):
    token = _token()
    first = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-456",
            "tool_id": "experiment.run_variant",
            "objective": {"goal": "first"},
        },
    )
    assert first.status_code == 200

    second = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-456",
            "tool_id": "experiment.run_variant",
            "objective": {"goal": "second"},
        },
    )
    assert second.status_code == 409


def test_external_agent_job_idempotent_replay_survives_runtime_contract_drift(
    client: TestClient, monkeypatch
):
    token = _token()
    payload = {
        "idempotency_key": "job-replay-contract-drift",
        "tool_id": "experiment.run_variant",
    }
    first = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json=payload,
    )
    assert first.status_code == 200

    monkeypatch.setattr("api.routes.external_agent_jobs.get_tool_spec", lambda _: None)

    replay = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json=payload,
    )
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True
    assert replay.json()["job"]["id"] == first.json()["job"]["id"]


def test_external_agent_job_duplicate_insert_reloads_existing_job(client: TestClient):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["run_variant"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
        principal_type="external_agent",
        principal_id="agent-ext-race",
        agent_profile_id="buyer-assistant-v1",
        idempotency_key="race-key",
        trace_id="trace_race_1",
    )
    first = create_external_agent_job(
        client_id=CLIENT_ID,
        principal_id="agent-ext-race",
        agent_profile_id="buyer-assistant-v1",
        idempotency_key="race-key",
        request_hash="same-request",
        run_id=run["id"],
        requested_skill_id="optimize-product-representation",
        requested_tool_id="experiment.run_variant",
        status="accepted",
        trace_id=run["trace_id"],
        request={"idempotency_key": "race-key"},
        response={"run_id": run["id"]},
    )
    second = create_external_agent_job(
        client_id=CLIENT_ID,
        principal_id="agent-ext-race",
        agent_profile_id="buyer-assistant-v1",
        idempotency_key="race-key",
        request_hash="same-request",
        run_id=run["id"],
        requested_skill_id="optimize-product-representation",
        requested_tool_id="experiment.run_variant",
        status="accepted",
        trace_id=run["trace_id"],
        request={"idempotency_key": "race-key"},
        response={"run_id": run["id"]},
    )
    assert second["id"] == first["id"]


def test_external_agent_job_route_conflict_returns_existing_run(
    client: TestClient, monkeypatch
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-route-race", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    first = created.json()
    existing = get_external_agent_job_by_idempotency_key(
        client_id=CLIENT_ID,
        principal_id="agent-ext-1",
        idempotency_key="job-route-race",
    )
    assert existing is not None
    deps = default_deps()
    run_count = len(deps.agent_runs.list_agent_runs(client_id=CLIENT_ID, limit=20))

    monkeypatch.setattr(
        "api.routes.external_agent_jobs.get_external_agent_job_by_idempotency_key",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "api.routes.external_agent_jobs.create_external_agent_job",
        lambda **_: existing,
    )
    replay = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-route-race", "tool_id": "experiment.run_variant"},
    )
    assert replay.status_code == 200
    payload = replay.json()
    assert payload["idempotent_replay"] is True
    assert payload["job"]["run_id"] == first["run"]["id"]
    assert payload["run"]["id"] == first["run"]["id"]
    assert len(deps.agent_runs.list_agent_runs(client_id=CLIENT_ID, limit=20)) == run_count


def test_external_agent_job_route_conflict_rechecks_request_hash(
    client: TestClient, monkeypatch
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-route-race-mismatch",
            "tool_id": "experiment.run_variant",
            "objective": {"goal": "first"},
        },
    )
    assert created.status_code == 200
    existing = get_external_agent_job_by_idempotency_key(
        client_id=CLIENT_ID,
        principal_id="agent-ext-1",
        idempotency_key="job-route-race-mismatch",
    )
    assert existing is not None
    deps = default_deps()
    run_count = len(deps.agent_runs.list_agent_runs(client_id=CLIENT_ID, limit=20))

    monkeypatch.setattr(
        "api.routes.external_agent_jobs.get_external_agent_job_by_idempotency_key",
        lambda **_: None,
    )
    monkeypatch.setattr(
        "api.routes.external_agent_jobs.create_external_agent_job",
        lambda **_: existing,
    )
    mismatch = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-route-race-mismatch",
            "tool_id": "experiment.run_variant",
            "objective": {"goal": "second"},
        },
    )
    assert mismatch.status_code == 409
    assert len(deps.agent_runs.list_agent_runs(client_id=CLIENT_ID, limit=20)) == run_count


def test_external_agent_job_requires_machine_auth_and_scopes(client: TestClient):
    unauthenticated = client.post(
        "/external-agent/jobs",
        json={"idempotency_key": "job-no-auth", "tool_id": "experiment.run_variant"},
    )
    assert unauthenticated.status_code == 401

    missing_job_scope = _token(scopes=["tool:experiment.run_variant"])
    no_job_scope = client.post(
        "/external-agent/jobs",
        headers=_headers(missing_job_scope),
        json={"idempotency_key": "job-no-scope", "tool_id": "experiment.run_variant"},
    )
    assert no_job_scope.status_code == 403

    missing_tool_scope = _token(scopes=["external_agent_jobs:write"])
    no_tool_scope = client.post(
        "/external-agent/jobs",
        headers=_headers(missing_tool_scope),
        json={"idempotency_key": "job-no-tool", "tool_id": "experiment.run_variant"},
    )
    assert no_tool_scope.status_code == 403


def test_external_agent_job_checks_scopes_for_allowed_capabilities(
    client: TestClient,
):
    missing_capability_tool_scope = _token(
        scopes=[
            "external_agent_jobs:write",
            "tool:experiment.run_variant",
            "skill:optimize-product-representation",
        ]
    )
    no_tool_scope = client.post(
        "/external-agent/jobs",
        headers=_headers(missing_capability_tool_scope),
        json={
            "idempotency_key": "job-capability-tool-scope",
            "allowed_capabilities": ["publish_copy_revision"],
        },
    )
    assert no_tool_scope.status_code == 403
    assert "copy.publish_revision" in no_tool_scope.json()["detail"]

    missing_capability_skill_scope = _token(
        scopes=[
            "external_agent_jobs:write",
            "tool:copy.publish_revision",
            "skill:optimize-product-representation",
        ]
    )
    no_skill_scope = client.post(
        "/external-agent/jobs",
        headers=_headers(missing_capability_skill_scope),
        json={
            "idempotency_key": "job-capability-skill-scope",
            "allowed_capabilities": ["publish_copy_revision"],
        },
    )
    assert no_skill_scope.status_code == 403
    assert "promote-and-publish-approved-copy" in no_skill_scope.json()["detail"]

    authorized = _token(
        scopes=[
            "external_agent_jobs:write",
            "tool:copy.publish_revision",
            "skill:promote-and-publish-approved-copy",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(authorized),
        json={
            "idempotency_key": "job-capability-authorized",
            "allowed_capabilities": ["publish_copy_revision"],
        },
    )
    assert created.status_code == 200
    assert created.json()["run"]["allowed_capabilities"] == ["publish_copy_revision"]


def test_external_agent_job_validates_requested_skill_tool_pair(client: TestClient):
    token = _token(scopes=["external_agent_jobs:write", "tools:*", "skills:*"])
    response = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={
            "idempotency_key": "job-bad-skill",
            "tool_id": "experiment.run_variant",
            "skill_id": "request-validation-and-ingest-result",
        },
    )
    assert response.status_code == 400
    assert "cannot use tool" in response.json()["detail"]


def test_external_agent_job_receipt_is_signed_and_tracks_run_status(
    client: TestClient,
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-receipt", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job"]["id"]
    run_id = payload["run"]["id"]

    receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert receipt_response.status_code == 200
    receipt = receipt_response.json()["receipt"]
    assert receipt["receipt_type"] == "external_agent_job_accepted"
    assert receipt["job_id"] == job_id
    assert receipt["run_id"] == run_id
    assert receipt["status"] == "accepted"
    assert receipt["signature_algorithm"] == "hmac-sha256"
    assert _valid_signature(receipt, "test-agent-secret")

    deps = default_deps()
    deps.agent_runs.update_agent_run(run_id=run_id, status="completed")
    completed_receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert completed_receipt_response.status_code == 200
    completed_receipt = completed_receipt_response.json()["receipt"]
    assert completed_receipt["receipt_type"] == "external_agent_job_completed"
    assert completed_receipt["status"] == "completed"
    assert completed_receipt["receipt_id"] != receipt["receipt_id"]
    assert _valid_signature(completed_receipt, "test-agent-secret")

    receipt_list = client.get(
        f"/external-agent/jobs/{job_id}/receipts", headers=_headers(token)
    )
    assert receipt_list.status_code == 200
    receipts = receipt_list.json()["receipts"]
    assert [item["status"] for item in receipts] == ["completed", "accepted"]
    assert all(_valid_signature(item, "test-agent-secret") for item in receipts)

    other_principal_token = _token(principal_id="agent-ext-receipt-other")
    wrong_principal = client.get(
        f"/external-agent/jobs/{job_id}/receipts",
        headers=_headers(other_principal_token),
    )
    assert wrong_principal.status_code == 404


def test_external_agent_job_status_hides_stale_receipt_metadata(client: TestClient):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-stale-receipt", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job"]["id"]
    run_id = payload["run"]["id"]

    receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert receipt_response.status_code == 200
    assert receipt_response.json()["receipt"]["status"] == "accepted"

    deps = default_deps()
    deps.agent_runs.update_agent_run(run_id=run_id, status="completed")

    status = client.get(f"/external-agent/jobs/{job_id}", headers=_headers(token))
    assert status.status_code == 200
    job = status.json()["job"]
    assert job["status"] == "completed"
    assert job["receipt_id"] is None
    assert job["receipt_type"] is None
    assert job["receipt_signature_algorithm"] is None

    completed_receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert completed_receipt_response.status_code == 200
    assert completed_receipt_response.json()["receipt"]["status"] == "completed"

    refreshed_status = client.get(f"/external-agent/jobs/{job_id}", headers=_headers(token))
    assert refreshed_status.status_code == 200
    refreshed_job = refreshed_status.json()["job"]
    assert refreshed_job["status"] == "completed"
    assert refreshed_job["receipt_type"] == "external_agent_job_completed"


def test_external_agent_job_receipt_insert_dedupes_status(client: TestClient):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-receipt-dedupe", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    job = payload["job"]
    run = payload["run"]
    receipt_response = client.get(
        f"/external-agent/jobs/{job['id']}/receipt", headers=_headers(token)
    )
    assert receipt_response.status_code == 200
    first_receipt = receipt_response.json()["receipt"]

    duplicate = create_external_agent_job_receipt(
        receipt_id="duplicate-receipt-id",
        job_id=job["id"],
        client_id=CLIENT_ID,
        principal_id="agent-ext-1",
        run_id=run["id"],
        receipt_type="external_agent_job_accepted",
        status="accepted",
        signature="duplicate-signature",
        signature_algorithm="hmac-sha256",
        payload={"receipt_id": "duplicate-receipt-id", "status": "accepted"},
    )
    assert duplicate["id"] == first_receipt["receipt_id"]

    receipt_list = client.get(
        f"/external-agent/jobs/{job['id']}/receipts", headers=_headers(token)
    )
    assert receipt_list.status_code == 200
    accepted = [
        item for item in receipt_list.json()["receipts"] if item["status"] == "accepted"
    ]
    assert len(accepted) == 1


def test_external_agent_job_status_and_receipt_normalize_canceled_run(
    client: TestClient,
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-canceled", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job"]["id"]
    run_id = payload["run"]["id"]

    deps = default_deps()
    deps.agent_runs.update_agent_run(run_id=run_id, status="canceled")

    status = client.get(f"/external-agent/jobs/{job_id}", headers=_headers(token))
    assert status.status_code == 200
    assert status.json()["job"]["status"] == "canceled"

    receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert receipt_response.status_code == 200
    receipt = receipt_response.json()["receipt"]
    assert receipt["receipt_type"] == "external_agent_job_canceled"
    assert receipt["status"] == "canceled"
    assert _valid_signature(receipt, "test-agent-secret")


def test_external_agent_job_status_preserves_paused_run(client: TestClient):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-paused", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job"]["id"]
    run_id = payload["run"]["id"]

    deps = default_deps()
    deps.agent_runs.update_agent_run(run_id=run_id, status="paused")

    status = client.get(f"/external-agent/jobs/{job_id}", headers=_headers(token))
    assert status.status_code == 200
    job = status.json()["job"]
    assert job["status"] == "paused"
    assert job["run_status"] == "paused"

    receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert receipt_response.status_code == 200
    receipt = receipt_response.json()["receipt"]
    assert receipt["receipt_type"] == "external_agent_job_paused"
    assert receipt["status"] == "paused"
    assert _valid_signature(receipt, "test-agent-secret")


def test_external_agent_job_events_are_scoped_to_creating_principal(
    client: TestClient,
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-events", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    job_id = created.json()["job"]["id"]

    events = client.get(
        f"/external-agent/jobs/{job_id}/events",
        headers=_headers(token),
        params={"event_type": "all"},
    )
    assert events.status_code == 200
    event_payload = events.json()
    assert event_payload["events"]
    assert event_payload["events"][0]["event_type"] == "action_proposed"
    assert event_payload["events"][0]["tool_id"] == "experiment.run_variant"

    other_principal_token = _token(principal_id="agent-ext-events-other")
    wrong_principal = client.get(
        f"/external-agent/jobs/{job_id}/events",
        headers=_headers(other_principal_token),
    )
    assert wrong_principal.status_code == 404


def test_external_agent_job_activity_projects_job_receipts_and_run_events(
    client: TestClient,
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-activity", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    job_id = created.json()["job"]["id"]

    receipt_response = client.get(
        f"/external-agent/jobs/{job_id}/receipt", headers=_headers(token)
    )
    assert receipt_response.status_code == 200

    activity = client.get(
        f"/external-agent/jobs/{job_id}/activity", headers=_headers(token)
    )
    assert activity.status_code == 200
    payload = activity.json()
    assert payload["summary"]["status"] == "accepted"
    assert payload["summary"]["receipt_count"] >= 1
    assert payload["summary"]["event_count"] >= 1
    item_types = {item["type"] for item in payload["items"]}
    assert {"job", "receipt", "run_event"}.issubset(item_types)
    run_event = next(item for item in payload["items"] if item["type"] == "run_event")
    assert run_event["subtype"] == "action_proposed"
    assert run_event["tool_id"] == "experiment.run_variant"
    assert payload["summary"]["page_scope"] == "run_events"
    assert payload["event_page"] == payload["page"]

    other_principal_token = _token(principal_id="agent-ext-activity-other")
    wrong_principal = client.get(
        f"/external-agent/jobs/{job_id}/activity",
        headers=_headers(other_principal_token),
    )
    assert wrong_principal.status_code == 404


def test_external_agent_job_activity_accepts_event_cursor_filters(
    client: TestClient,
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(token),
        json={"idempotency_key": "job-activity-cursors", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    job_id = payload["job"]["id"]
    run_id = payload["run"]["id"]

    deps = default_deps()
    time.sleep(1.05)
    deps.agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=None,
        sequence=99,
        event_type="operator_command_completed",
        status="completed",
        capability_name=None,
        capability_version=None,
        note="Cursor filter marker",
        anchors={},
    )

    first = client.get(
        f"/external-agent/jobs/{job_id}/activity",
        headers=_headers(token),
        params={"limit": 1, "event_type": "command"},
    )
    assert first.status_code == 200
    first_payload = first.json()
    command_events = [
        item for item in first_payload["items"] if item["type"] == "run_event"
    ]
    assert len(command_events) == 1
    assert command_events[0]["subtype"] == "operator_command_completed"
    assert first_payload["event_page"]["after_cursor"]

    next_page = client.get(
        f"/external-agent/jobs/{job_id}/activity",
        headers=_headers(token),
        params={
            "limit": 1,
            "event_type": "all",
            "before": first_payload["event_page"]["before_cursor"],
        },
    )
    assert next_page.status_code == 200
    next_payload = next_page.json()
    next_events = [item for item in next_payload["items"] if item["type"] == "run_event"]
    assert len(next_events) == 1
    assert next_events[0]["subtype"] == "action_proposed"


def _valid_signature(receipt: dict, secret: str) -> bool:
    signature = receipt["signature"]
    payload_b64, provided_signature = signature.rsplit(".", 1)
    expected_signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(provided_signature, expected_signature):
        return False
    padding = "=" * (-len(payload_b64) % 4)
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + padding))
    unsigned_receipt = {
        key: value
        for key, value in receipt.items()
        if key not in {"signature", "signature_algorithm"}
    }
    return payload == unsigned_receipt
