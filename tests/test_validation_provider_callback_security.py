from __future__ import annotations

import sys
import time
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
import infrastructure.db.catalog.clients as clients_repo


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("ENABLE_PROVIDER_VALIDATION_INTEGRATIONS", "true")
    monkeypatch.setenv("VALIDATION_CALLBACK_SIGNING_SECRET", "test-signing-secret")
    monkeypatch.setenv("VALIDATION_CALLBACK_TTL_SECONDS", "1")
    get_settings.cache_clear()

    db_path = tmp_path / "validation-provider-security.db"
    set_database_path(db_path)
    init_db()
    clients_repo.create_client(client_id="client-a", name="Client A")

    # Rebuild validation service so adapter reads refreshed settings.
    import api.routes.validation as validation_route

    validation_route.SERVICE = ValidationService(deps=default_deps())
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


def _start_provider_run(client: TestClient, job_id: str) -> dict:
    response = client.post(
        f"/validation/jobs/{job_id}/start-provider-run",
        json={"client_id": "client-a"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload.get("provider_run_id")
    assert payload.get("callback_token")
    return payload


def test_provider_callback_valid_once_then_replay_rejected(client: TestClient):
    job_id = _create_provider_job(client)
    start = _start_provider_run(client, job_id)

    body = {
        "provider_run_id": start["provider_run_id"],
        "callback_signature": start["callback_token"],
        "structured_result": {
            "winner_id": "variant-a",
            "score": 0.74,
            "confidence": 0.83,
            "evidence_strength": "moderate",
        },
    }
    first = client.post(f"/validation/jobs/{job_id}/provider-callback", json=body)
    assert first.status_code == 200

    replay = client.post(f"/validation/jobs/{job_id}/provider-callback", json=body)
    assert replay.status_code == 409
    assert "replay" in replay.json()["detail"].lower()


def test_provider_callback_rejects_wrong_provider_run_id(client: TestClient):
    job_id = _create_provider_job(client)
    start = _start_provider_run(client, job_id)

    response = client.post(
        f"/validation/jobs/{job_id}/provider-callback",
        json={
            "provider_run_id": "wrong-run-id",
            "callback_signature": start["callback_token"],
            "structured_result": {
                "winner_id": "variant-a",
                "score": 0.74,
                "confidence": 0.83,
                "evidence_strength": "moderate",
            },
        },
    )
    assert response.status_code == 400
    assert "provider_run_id mismatch" in response.json()["detail"]


def test_provider_callback_rejects_expired_token(client: TestClient):
    job_id = _create_provider_job(client)
    start = _start_provider_run(client, job_id)
    time.sleep(2)

    response = client.post(
        f"/validation/jobs/{job_id}/provider-callback",
        json={
            "provider_run_id": start["provider_run_id"],
            "callback_signature": start["callback_token"],
            "structured_result": {
                "winner_id": "variant-a",
                "score": 0.74,
                "confidence": 0.83,
                "evidence_strength": "moderate",
            },
        },
    )
    assert response.status_code == 401
    assert "invalid callback signature/token" in response.json()["detail"].lower()
