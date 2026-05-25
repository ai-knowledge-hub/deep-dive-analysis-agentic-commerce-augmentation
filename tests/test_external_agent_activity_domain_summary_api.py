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
from application.services.agent_runtime.runtime.service import AgentRuntimeService
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


def _token(*, scopes: list[str] | None = None) -> str:
    return build_agent_principal_token(
        principal_id="agent-ext-1",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=scopes or [
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:experiment.run_variant",
            "skill:optimize-product-representation",
        ],
    )


def test_external_agent_job_can_seed_protocol_discovery_single_tool(
    client: TestClient,
):
    token = _token(
        scopes=[
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:protocol.discover_candidates",
            "skill:discover-protocol-candidates",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idempotency_key": "job-protocol-discovery-single-tool",
            "tool_id": "protocol.discover_candidates",
            "objective": {
                "query": "blue running shoe",
                "protocol": "ucp",
                "limit": 7,
            },
        },
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["run"]["allowed_capabilities"] == [
        "discover_protocol_candidates"
    ]
    assert payload["run"]["objective"]["plan_mode"] == "single_tool"

    actions = default_deps().agent_actions.list_agent_actions(
        agent_run_id=payload["run"]["id"], limit=10
    )
    assert [action["capability_name"] for action in actions] == [
        "discover_protocol_candidates"
    ]
    assert actions[0]["inputs"] == {
        "query": "blue running shoe",
        "protocol": "ucp",
        "limit": 7,
    }
    assert actions[0]["tool_id"] == "protocol.discover_candidates"
    assert actions[0]["skill_id"] == "discover-protocol-candidates"


def test_external_agent_protocol_discovery_requires_query(client: TestClient):
    token = _token(
        scopes=[
            "external_agent_jobs:write",
            "tool:protocol.discover_candidates",
            "skill:discover-protocol-candidates",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idempotency_key": "job-protocol-discovery-missing-query",
            "tool_id": "protocol.discover_candidates",
            "objective": {"protocol": "ucp"},
        },
    )

    assert created.status_code == 400
    assert created.json()["detail"]["code"] == "invalid_job_plan"


def test_external_agent_activity_summarizes_protocol_discovery(
    client: TestClient,
):
    deps = default_deps()
    deps.clients.create_brand(brand_id="brand-a", client_id=CLIENT_ID, name="Brand A")
    deps.clients.create_product(
        product_id="product-a",
        brand_id="brand-a",
        name="Blue Runner",
        description="Daily blue running shoe.",
        metadata={
            "ucp": {
                "offer_url": "https://example.test/p/blue-runner",
                "price": 129.0,
                "availability": "in_stock",
            }
        },
    )
    token = _token(
        scopes=[
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:protocol.discover_candidates",
            "skill:discover-protocol-candidates",
        ]
    )
    created = client.post(
        "/external-agent/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "idempotency_key": "job-activity-protocol-discovery",
            "tool_id": "protocol.discover_candidates",
            "objective": {"query": "blue running shoe", "protocol": "ucp"},
        },
    )
    assert created.status_code == 200
    payload = created.json()
    action = deps.agent_actions.list_agent_actions(
        agent_run_id=payload["run"]["id"], limit=10
    )[0]
    deps.agent_actions.transition_agent_action_status(
        action_id=action["id"],
        from_status="proposed",
        to_status="approved",
    )
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=payload["run"]["id"], user_id="agent-ext-1"
    )
    assert result.action is not None
    assert result.action["status"] == "executed"

    activity = client.get(
        f"/external-agent/jobs/{payload['job']['id']}/activity",
        headers={"Authorization": f"Bearer {token}"},
        params={"capability_name": "discover_protocol_candidates"},
    )
    assert activity.status_code == 200
    protocol_event = next(
        item
        for item in activity.json()["items"]
        if item.get("subtype") == "action_executed"
        and item.get("capability_name") == "discover_protocol_candidates"
    )
    assert protocol_event["domain_summary"]["receipt_id"]
    assert protocol_event["domain_summary"] == {
        "domain": "protocol_discovery",
        "readiness_status": "blocked",
        "readiness_score": 0,
        "candidate_count": 1,
        "source_counts": {"ucp_local_metadata": 1},
        "live_source_count": 0,
        "local_source_count": 1,
        "receipt_id": protocol_event["domain_summary"]["receipt_id"],
    }
