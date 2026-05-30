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
    set_database_path(tmp_path / "external-agent-job-errors.db")
    init_db()
    default_deps().clients.create_client(client_id=CLIENT_ID, name="Client A")
    return TestClient(app)


def _headers() -> dict[str, str]:
    token = build_agent_principal_token(
        principal_id="agent-ext-1",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=["external_agent_jobs:read"],
    )
    return {"Authorization": f"Bearer {token}"}


def test_external_agent_job_missing_status_uses_stable_error_code(
    client: TestClient,
):
    response = client.get("/external-agent/jobs/job-missing", headers=_headers())
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "external_agent_job_not_found"
    assert detail["retryable"] is False
    assert detail["context"] == {"job_id": "job-missing"}


def test_external_agent_job_missing_receipt_uses_stable_job_error_code(
    client: TestClient,
):
    response = client.get(
        "/external-agent/jobs/job-missing/receipt", headers=_headers()
    )
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert detail["code"] == "external_agent_job_not_found"
    assert detail["retryable"] is False
    assert detail["context"] == {"job_id": "job-missing"}
