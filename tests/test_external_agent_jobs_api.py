from __future__ import annotations

import sys
import types
import base64
import hashlib
import hmac
import json

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
from infrastructure.db.agent.external_agent_jobs import create_external_agent_job
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

    other_principal_token = _token(principal_id="agent-ext-activity-other")
    wrong_principal = client.get(
        f"/external-agent/jobs/{job_id}/activity",
        headers=_headers(other_principal_token),
    )
    assert wrong_principal.status_code == 404


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
