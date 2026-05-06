from __future__ import annotations

import sys
import types

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
