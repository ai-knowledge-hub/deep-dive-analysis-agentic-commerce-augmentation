from __future__ import annotations

from fastapi.testclient import TestClient

from api.main import app


def test_external_agent_credential_metadata_exposes_scope_contract():
    client = TestClient(app)

    response = client.get("/external-agent/credentials/metadata")

    assert response.status_code == 200
    payload = response.json()
    assert payload["scope_claim"] == "scopes"
    assert payload["scope_wildcards"] == ["*", "tools:*", "skills:*"]
    assert {
        "scope": "tool:<tool_id>",
        "kind": "tool",
        "grants": "request one registry tool through external-agent jobs",
        "wildcard": "tools:*",
        "required_for": ["POST /external-agent/jobs"],
    } in payload["scope_catalog"]
    assert {
        "scope": "skill:<skill_id>",
        "kind": "skill",
        "grants": "request one registry skill or the default skill selected for a tool",
        "wildcard": "skills:*",
        "required_for": ["POST /external-agent/jobs"],
    } in payload["scope_catalog"]
    assert payload["registry_scope_discovery"] == {
        "endpoint": "GET /agent-runs/registry",
        "tool_contract_path": "tools[].external_agent_contract.required_scopes",
        "capability_contract_path": "capabilities[].external_agent_contract.required_scopes",
        "readiness_boundary_path": "readiness_boundaries[]",
    }
    assert {
        "name": "read-only protocol discovery job",
        "scopes": [
            "external_agent_jobs:write",
            "external_agent_jobs:read",
            "tool:protocol.discover_candidates",
            "skill:discover-protocol-candidates",
        ],
    } in payload["least_privilege_examples"]
