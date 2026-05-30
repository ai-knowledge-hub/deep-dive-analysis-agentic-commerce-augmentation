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
    set_database_path(tmp_path / "external-agent-activity-summaries.db")
    init_db()
    default_deps().clients.create_client(client_id=CLIENT_ID, name="Client A")
    return TestClient(app)


def _headers() -> dict[str, str]:
    token = build_agent_principal_token(
        principal_id="agent-ext-1",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=[
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:experiment.run_variant",
            "skill:optimize-product-representation",
        ],
    )
    return {"Authorization": f"Bearer {token}"}


def test_external_agent_activity_summarizes_runtime_stopping_conditions(
    client: TestClient,
):
    created = client.post(
        "/external-agent/jobs",
        headers=_headers(),
        json={"idempotency_key": "job-stop-summary", "tool_id": "experiment.run_variant"},
    )
    assert created.status_code == 200
    payload = created.json()
    run_id = payload["run"]["id"]
    job_id = payload["job"]["id"]

    default_deps().agent_events.create_agent_event(
        agent_run_id=run_id,
        action_id=None,
        sequence=2,
        event_type="run_stopping_condition_met",
        status="paused",
        capability_name=None,
        capability_version=None,
        note="Run paused because policy blocked an action.",
        anchors={"stopping_condition": "policy_block"},
    )

    activity = client.get(f"/external-agent/jobs/{job_id}/activity", headers=_headers())
    assert activity.status_code == 200
    stop_item = next(
        item
        for item in activity.json()["items"]
        if item["subtype"] == "run_stopping_condition_met"
    )
    assert stop_item["domain_summary"] == {
        "domain": "runtime_stopping_condition",
        "stopping_condition": "policy_block",
        "outcome_status": "paused",
        "operator_attention_required": True,
        "terminal": False,
        "note": "Run paused because policy blocked an action.",
    }
