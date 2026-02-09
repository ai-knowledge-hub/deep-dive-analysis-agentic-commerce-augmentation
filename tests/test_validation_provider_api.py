from __future__ import annotations

import sys
import types

from fastapi.testclient import TestClient
import pytest

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
from application.services.validation_service import ValidationService
from shared.config.env import get_settings
from shared.db.connection import init_db, set_database_path
from infrastructure.db import clients as clients_repo


def _reset_validation_service() -> None:
    import api.routes.validation as validation_route

    validation_route.SERVICE = ValidationService(deps=default_deps())


@pytest.fixture
def client_flag_off(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_PROVIDER_VALIDATION_INTEGRATIONS", "false")
    monkeypatch.setenv("VALIDATION_CALLBACK_SIGNING_SECRET", "test-signing-secret")
    get_settings.cache_clear()
    db_path = tmp_path / "validation-provider-api-off.db"
    set_database_path(db_path)
    init_db()
    clients_repo.create_client(client_id="client-a", name="Client A")
    _reset_validation_service()
    return TestClient(app)


@pytest.fixture
def client_flag_on(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_PROVIDER_VALIDATION_INTEGRATIONS", "true")
    monkeypatch.setenv("VALIDATION_CALLBACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("VALIDATION_CALLBACK_TTL_SECONDS", "30")
    monkeypatch.setenv("OPENAI_MCP_LAUNCH_URL", "https://chatgpt.com")
    monkeypatch.setenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
    get_settings.cache_clear()
    db_path = tmp_path / "validation-provider-api-on.db"
    set_database_path(db_path)
    init_db()
    clients_repo.create_client(client_id="client-a", name="Client A")
    _reset_validation_service()
    return TestClient(app)


def _create_provider_job(client: TestClient) -> str:
    response = client.post(
        "/validation/jobs",
        json={
            "client_id": "client-a",
            "entity_type": "experiment_run",
            "entity_id": "exp-1",
            "provider": "openai",
            "mode": "provider_openai_mcp",
            "input_payload": {"type": "experiment"},
        },
    )
    assert response.status_code == 200
    return response.json()["job"]["id"]


def test_start_provider_run_returns_501_when_flag_disabled(client_flag_off: TestClient):
    job_id = _create_provider_job(client_flag_off)
    response = client_flag_off.post(
        f"/validation/jobs/{job_id}/start-provider-run",
        json={"client_id": "client-a"},
    )
    assert response.status_code == 501
    assert "not enabled" in response.json()["detail"].lower()


def test_provider_callback_returns_501_when_flag_disabled(client_flag_off: TestClient):
    job_id = _create_provider_job(client_flag_off)
    response = client_flag_off.post(
        f"/validation/jobs/{job_id}/provider-callback",
        json={
            "provider_run_id": "run-1",
            "callback_signature": "invalid",
            "structured_result": {
                "winner_id": "variant-a",
                "score": 0.7,
                "confidence": 0.8,
                "evidence_strength": "moderate",
            },
        },
    )
    assert response.status_code == 501
    assert "not enabled" in response.json()["detail"].lower()


def test_provider_endpoints_success_with_flag_enabled(client_flag_on: TestClient):
    job_id = _create_provider_job(client_flag_on)
    start = client_flag_on.post(
        f"/validation/jobs/{job_id}/start-provider-run",
        json={"client_id": "client-a"},
    )
    assert start.status_code == 200
    payload = start.json()
    assert payload["provider_run_id"]
    assert payload["launch_url"]
    assert payload["callback_token"]
    assert payload["setup_url"]

    callback = client_flag_on.post(
        f"/validation/jobs/{job_id}/provider-callback",
        json={
            "provider_run_id": payload["provider_run_id"],
            "callback_signature": payload["callback_token"],
            "structured_result": {
                "winner_id": "variant-a",
                "score": 0.74,
                "confidence": 0.83,
                "evidence_strength": "moderate",
            },
        },
    )
    assert callback.status_code == 200
    result = callback.json()["result"]
    assert result["source"] == "provider_openai_mcp"
