from __future__ import annotations

import sys
import types

from fastapi.testclient import TestClient
import pytest

if "google" not in sys.modules:
    google_pkg = types.ModuleType("google")
    genai_pkg = types.ModuleType("google.genai")
    genai_types_pkg = types.ModuleType("google.genai.types")

    class DummyClient:
        def __init__(self, *args, **kwargs):
            self.models = types.SimpleNamespace(
                generate_content=lambda **_: types.SimpleNamespace(text="")
            )

    genai_pkg.Client = DummyClient
    genai_pkg.types = genai_types_pkg
    google_pkg.genai = genai_pkg
    sys.modules["google"] = google_pkg
    sys.modules["google.genai"] = genai_pkg
    sys.modules["google.genai.types"] = genai_types_pkg

from api.main import app
from shared.db.connection import init_db, set_database_path
import infrastructure.db.catalog.clients as clients_repo


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "learning-loop.db"
    set_database_path(db_path)
    init_db()
    clients_repo.create_client(client_id="client-a", name="Client A")
    clients_repo.create_client(client_id="client-b", name="Client B")
    return TestClient(app)


def test_beliefs_update_creates_revision(client: TestClient):
    response = client.post(
        "/beliefs/update",
        json={
            "client_id": "client-a",
            "hypothesis_key": "copy:discoverability",
            "evidence": {
                "source": "observed",
                "score": 0.8,
                "confidence": 0.9,
                "winner_id": "candidate",
            },
        },
    )
    assert response.status_code == 200
    revision = response.json()["revision"]
    assert revision["id"]
    assert revision["hypothesis_key"] == "copy:discoverability"
    assert 0 <= revision["posterior"] <= 1
    assert 0 <= revision["confidence"] <= 1

    list_response = client.get("/beliefs/revisions?client_id=client-a")
    assert list_response.status_code == 200
    assert len(list_response.json()["revisions"]) >= 1


def test_validation_external_auto_creates_belief_revision_and_loop_state(
    client: TestClient,
):
    create_job = client.post(
        "/validation/jobs",
        json={
            "client_id": "client-a",
            "entity_type": "experiment_run",
            "entity_id": "exp-1",
            "provider": "openrouter",
            "mode": "external",
            "input_payload": {"type": "experiment"},
        },
    )
    assert create_job.status_code == 200
    job_id = create_job.json()["job"]["id"]

    submit_external = client.post(
        f"/validation/jobs/{job_id}/external",
        json={
            "client_id": "client-a",
            "structured_result": {
                "winner_id": "variant-a",
                "score": 0.72,
                "confidence": 0.81,
                "evidence_strength": "moderate",
            },
        },
    )
    assert submit_external.status_code == 200

    revisions = client.get(
        "/beliefs/revisions?client_id=client-a&hypothesis_key=validation:experiment_run:exp-1"
    )
    assert revisions.status_code == 200
    payload = revisions.json()["revisions"]
    assert len(payload) == 1
    assert payload[0]["evidence_ref"]["validation_job_id"] == job_id

    loop_state = client.get("/loop/state?client_id=client-a")
    assert loop_state.status_code == 200
    state_payload = loop_state.json()
    assert state_payload["latest_belief_revision"] is not None
    assert state_payload["latest_decision"] is not None
    assert state_payload["state"] is not None


def test_tenant_isolation_on_belief_revisions(client: TestClient):
    update_response = client.post(
        "/beliefs/update",
        json={
            "client_id": "client-a",
            "hypothesis_key": "tenant:test",
            "evidence": {"source": "synthetic", "score": 0.6, "confidence": 0.6},
        },
    )
    assert update_response.status_code == 200

    revisions_a = client.get("/beliefs/revisions?client_id=client-a")
    revisions_b = client.get("/beliefs/revisions?client_id=client-b")
    assert revisions_a.status_code == 200
    assert revisions_b.status_code == 200
    assert len(revisions_a.json()["revisions"]) >= 1
    assert revisions_b.json()["revisions"] == []


def test_loop_step_and_calibration_profile_routes(client: TestClient):
    upsert = client.post(
        "/calibration/profile",
        json={
            "client_id": "client-a",
            "provider": "openrouter",
            "metric_weights": {"uncertainty_weight": 1.4, "gain_weight": 0.8},
            "drift_score": 0.25,
        },
    )
    assert upsert.status_code == 200
    profile = upsert.json()["profile"]
    assert profile["provider"] == "openrouter"

    get_profile = client.get(
        "/calibration/profile?client_id=client-a&provider=openrouter"
    )
    assert get_profile.status_code == 200
    assert get_profile.json()["profile"]["provider"] == "openrouter"

    loop_step = client.post(
        "/loop/step",
        json={
            "client_id": "client-a",
            "provider": "openrouter",
            "uncertainty": 0.8,
            "expected_gain": 0.7,
        },
    )
    assert loop_step.status_code == 200
    payload = loop_step.json()
    assert payload["recommended_action"]
    assert payload["decision"]["policy_action"] == payload["recommended_action"]

    metrics = client.get("/loop/metrics?client_id=client-a")
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    assert "update_frequency" in metrics_payload
    assert "drift_trend" in metrics_payload
    assert "action_distribution" in metrics_payload
    assert "loop_health" in metrics_payload
    assert "acceptance_rate" in metrics_payload["loop_health"]
    assert "regeneration_rate" in metrics_payload["loop_health"]
    assert "observed_vs_synthetic_agreement" in metrics_payload["loop_health"]


def test_validation_external_rejects_out_of_range_score(client: TestClient):
    create_job = client.post(
        "/validation/jobs",
        json={
            "client_id": "client-a",
            "entity_type": "experiment_run",
            "entity_id": "exp-bounds",
            "provider": "openrouter",
            "mode": "external",
            "input_payload": {"type": "experiment"},
        },
    )
    assert create_job.status_code == 200
    job_id = create_job.json()["job"]["id"]

    submit_external = client.post(
        f"/validation/jobs/{job_id}/external",
        json={
            "client_id": "client-a",
            "structured_result": {
                "winner_id": "variant-a",
                "score": 1.4,
                "confidence": 0.81,
                "evidence_strength": "moderate",
            },
        },
    )
    assert submit_external.status_code == 400
    assert "score" in submit_external.json()["detail"].lower()
