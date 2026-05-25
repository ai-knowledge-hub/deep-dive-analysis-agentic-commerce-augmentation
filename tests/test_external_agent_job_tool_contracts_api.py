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
    set_database_path(tmp_path / "external-agent-tool-contracts-api.db")
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
        scopes=["external_agent_jobs:write", "tools:*", "skills:*"],
    )


def test_external_agent_job_distinguishes_non_executable_from_unknown_tool(
    client: TestClient,
):
    headers = {"Authorization": f"Bearer {_token()}"}
    non_executable = client.post(
        "/external-agent/jobs",
        headers=headers,
        json={"idempotency_key": "job-non-executable", "tool_id": "protocol.ucp.checkout"},
    )
    assert non_executable.status_code == 400
    detail = non_executable.json()["detail"]
    assert detail["code"] == "declared_non_executable_tool"
    assert detail["retryable"] is False
    assert detail["context"]["tool_id"] == "protocol.ucp.checkout"
    assert detail["context"]["executable"] is False
    assert detail["context"]["adapter_id"] == "protocol.checkout.v1"
    assert detail["context"]["contract_intent"] == "readiness_boundary"
    assert (
        detail["context"]["blocked_reason"]
        == "readiness_boundary_only_no_transaction_execution"
    )
    assert detail["context"]["receipt_contract"]["receipt_type"] == (
        "external_write_execution"
    )

    unknown = client.post(
        "/external-agent/jobs",
        headers=headers,
        json={"idempotency_key": "job-unknown-tool", "tool_id": "not.real"},
    )
    assert unknown.status_code == 400
    assert unknown.json()["detail"]["code"] == "unsupported_tool"
