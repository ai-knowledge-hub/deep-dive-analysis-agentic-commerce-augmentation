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
from shared.db.connection import init_db, set_database_path

CLIENT_ID = "client-a"
USER_ID = "user-a"


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "agent-runs-api.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=CLIENT_ID, name="Client A")
    return TestClient(app)


def _seed_run_with_events() -> tuple[dict, list[dict]]:
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["run_variant", "seed_hypotheses"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="variants_ready",
        status="running",
    )
    seeded_events: list[dict] = []
    rows = [
        ("run_variant", "executed", False),
        ("run_variant", "failed", True),
        ("seed_hypotheses", "failed", False),
        ("run_variant", "failed", False),
    ]
    for idx, (capability, status, is_policy_event) in enumerate(rows, start=1):
        action = deps.agent_actions.create_agent_action(
            agent_run_id=run["id"],
            sequence=idx,
            status=status,
            capability_name=capability,
            capability_version="v1",
            inputs={},
            outputs={},
            inputs_hash=f"in-{idx}",
            outputs_hash=f"out-{idx}",
            rationale=f"action {idx}",
            confidence=0.5,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
        )
        event = deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=action["id"],
            sequence=idx,
            event_type=f"action_{status}",
            status=status,
            capability_name=capability,
            capability_version="v1",
            note=f"event {idx}",
            is_policy_event=is_policy_event,
            anchors={},
        )
        seeded_events.append(event)
    return run, seeded_events


def test_agent_run_events_endpoint_supports_filter_and_cursor(client: TestClient):
    run, _ = _seed_run_with_events()

    first = client.get(
        f"/agent-runs/{run['id']}/events",
        params={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "event_type": "all",
            "status": "failed",
            "capability_name": "run_variant",
            "limit": 1,
        },
    )
    assert first.status_code == 200
    payload_1 = first.json()
    assert len(payload_1["events"]) == 1
    assert payload_1["events"][0]["status"] == "failed"
    assert payload_1["events"][0]["capability_name"] == "run_variant"
    assert payload_1["page"]["before_cursor"]
    assert payload_1["page"]["has_more_before"] is True

    second = client.get(
        f"/agent-runs/{run['id']}/events",
        params={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "event_type": "all",
            "status": "failed",
            "capability_name": "run_variant",
            "limit": 1,
            "before": payload_1["page"]["before_cursor"],
        },
    )
    assert second.status_code == 200
    payload_2 = second.json()
    assert len(payload_2["events"]) == 1
    assert payload_2["events"][0]["status"] == "failed"
    assert payload_2["events"][0]["capability_name"] == "run_variant"


def test_agent_run_events_endpoint_supports_event_centering(client: TestClient):
    run, events = _seed_run_with_events()
    anchor_event_id = events[2]["id"]

    response = client.get(
        f"/agent-runs/{run['id']}/events",
        params={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "event_type": "all",
            "event_id": anchor_event_id,
            "around": 3,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    ids = [item["id"] for item in payload["events"]]
    assert anchor_event_id in ids
    assert len(ids) <= 3


def test_agent_run_events_endpoint_returns_404_when_event_not_in_filter(
    client: TestClient,
):
    run, events = _seed_run_with_events()
    failed_event_id = events[1]["id"]

    response = client.get(
        f"/agent-runs/{run['id']}/events",
        params={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "event_type": "all",
            "status": "executed",
            "event_id": failed_event_id,
            "around": 5,
        },
    )
    assert response.status_code == 404
