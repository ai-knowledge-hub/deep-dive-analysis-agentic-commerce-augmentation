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
    set_database_path(tmp_path / "external-agent-activity-domain-summary-api.db")
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=CLIENT_ID, name="Client A")
    return TestClient(app)


def _token() -> str:
    return build_agent_principal_token(
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


def test_external_agent_activity_summarizes_protocol_discovery(
    client: TestClient,
):
    token = _token()
    created = client.post(
        "/external-agent/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idempotency_key": "job-activity-protocol-discovery",
            "tool_id": "experiment.run_variant",
            "objective": {"query": "blue running shoe"},
        },
    )
    assert created.status_code == 200
    payload = created.json()

    default_deps().agent_events.create_agent_event(
        agent_run_id=payload["run"]["id"],
        action_id=None,
        sequence=2,
        event_type="action_executed",
        status="completed",
        capability_name="discover_protocol_candidates",
        capability_version="v1",
        tool_id="protocol.discover_candidates",
        skill_id="discover-protocol-candidates",
        effect_class="read",
        trace_id=payload["job"]["trace_id"],
        anchors={
            "receipt_id": "receipt-protocol-discovery",
            "receipt": {
                "receipt_id": "receipt-protocol-discovery",
                "evidence": {
                    "candidate_count": 3,
                    "source_counts": {
                        "acp_product_feed": 2,
                        "ucp_local_metadata": 1,
                    },
                    "readiness_summary": {
                        "status": "needs_review",
                        "score": 67,
                        "candidate_count": 3,
                        "live_source_count": 2,
                        "local_source_count": 1,
                    },
                },
            },
        },
    )

    activity = client.get(
        f"/external-agent/jobs/{payload['job']['id']}/activity",
        headers={"Authorization": f"Bearer {token}"},
        params={"capability_name": "discover_protocol_candidates"},
    )
    assert activity.status_code == 200
    protocol_event = next(
        item
        for item in activity.json()["items"]
        if item.get("capability_name") == "discover_protocol_candidates"
    )
    assert protocol_event["domain_summary"] == {
        "domain": "protocol_discovery",
        "readiness_status": "needs_review",
        "readiness_score": 67,
        "candidate_count": 3,
        "source_counts": {
            "acp_product_feed": 2,
            "ucp_local_metadata": 1,
        },
        "live_source_count": 2,
        "local_source_count": 1,
        "receipt_id": "receipt-protocol-discovery",
    }
