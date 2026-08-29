from __future__ import annotations

import base64
import hashlib
import hmac
import json
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
from infrastructure.db.core.connection import get_connection
from shared.config.env import get_settings
from shared.db.connection import init_db, set_database_path

CLIENT_ID = "client-a"
USER_ID = "user-a"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    get_settings.cache_clear()
    db_path = tmp_path / "agent-run-external-auth.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=CLIENT_ID, name="Client A")
    deps.users.ensure_user(USER_ID)
    deps.clients.add_client_user(
        client_id=CLIENT_ID, user_id=USER_ID, role="operator"
    )
    return TestClient(app)


def test_external_agent_owned_run_allows_operator_supervision_and_owner_bearer_scope(
    client: TestClient,
):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"goal": "external owner control"},
        allowed_capabilities=["seed_hypotheses"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="running",
        principal_type="external_agent",
        principal_id="agent-owner",
        agent_profile_id="buyer-assistant-v1",
        trace_id="trace_external_owner_control",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="proposed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash="seed-in",
        outputs_hash=None,
        rationale="external proposed action",
        confidence=0.7,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )

    wrong_principal_token = build_agent_principal_token(
        principal_id="agent-other",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:write"],
    )
    wrong_principal = client.post(
        f"/agent-runs/actions/{action['id']}/decision",
        headers={"Authorization": f"Bearer {wrong_principal_token}"},
        json={"client_id": CLIENT_ID, "decision": "approve"},
    )
    assert wrong_principal.status_code == 403

    missing_scope_token = build_agent_principal_token(
        principal_id="agent-owner",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:read"],
    )
    missing_scope = client.post(
        f"/agent-runs/actions/{action['id']}/decision",
        headers={"Authorization": f"Bearer {missing_scope_token}"},
        json={"client_id": CLIENT_ID, "decision": "approve"},
    )
    assert missing_scope.status_code == 403

    owner_token = build_agent_principal_token(
        principal_id="agent-owner",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:write"],
    )
    approved = client.post(
        f"/agent-runs/actions/{action['id']}/decision",
        headers={"Authorization": f"Bearer {owner_token}"},
        json={"client_id": CLIENT_ID, "decision": "approve"},
    )
    assert approved.status_code == 200
    assert approved.json()["action"]["status"] == "approved"

    operator_action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="proposed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash="seed-in-2",
        outputs_hash=None,
        rationale="operator supervised action",
        confidence=0.7,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    human_shaped_decision = client.post(
        f"/agent-runs/actions/{operator_action['id']}/decision",
        json={"client_id": CLIENT_ID, "user_id": USER_ID, "decision": "approve"},
    )
    assert human_shaped_decision.status_code == 200
    assert human_shaped_decision.json()["action"]["status"] == "approved"

    human_shaped_pause = client.post(
        f"/agent-runs/{run['id']}/pause",
        json={"client_id": CLIENT_ID, "user_id": USER_ID},
    )
    assert human_shaped_pause.status_code == 200
    assert human_shaped_pause.json()["run"]["status"] == "paused"

    tenant_only_pause = client.post(
        f"/agent-runs/{run['id']}/pause",
        json={"client_id": CLIENT_ID},
    )
    assert tenant_only_pause.status_code == 401


def test_bearer_principal_cannot_use_parameter_tenancy_for_human_run(
    client: TestClient,
):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"goal": "human run"},
        allowed_capabilities=["seed_hypotheses"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
        principal_type="human",
        principal_id="human:user-a",
        trace_id="trace_human_run",
    )
    token = build_agent_principal_token(
        principal_id="agent-reader",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:read"],
    )

    detail = client.get(
        f"/agent-runs/{run['id']}",
        headers={"Authorization": f"Bearer {token}"},
        params={"client_id": CLIENT_ID},
    )
    assert detail.status_code == 403

    listing = client.get(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        params={"client_id": CLIENT_ID},
    )
    assert listing.status_code == 200
    assert all(item["id"] != run["id"] for item in listing.json()["runs"])

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"client_id": CLIENT_ID},
    )
    assert events.status_code == 403


def test_create_external_agent_run_requires_bearer_principal(client: TestClient):
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "principal_type": "external_agent",
            "principal_id": "principal-ext-1",
            "agent_profile_id": "external-buyer-assistant",
            "allowed_capabilities": ["run_variant"],
            "run_mode": "auto_execute_safe",
        },
    )
    assert response.status_code == 401

    token = build_agent_principal_token(
        principal_id="other-principal",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:write"],
    )
    mismatch = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "client_id": CLIENT_ID,
            "principal_type": "external_agent",
            "principal_id": "principal-ext-1",
            "allowed_capabilities": ["run_variant"],
        },
    )
    assert mismatch.status_code == 403


def test_agent_principal_token_requires_exp_claim(client: TestClient):
    token = _legacy_agent_principal_token(
        {
            "principal_id": "legacy-principal",
            "client_id": CLIENT_ID,
            "principal_type": "external_agent",
            "scopes": ["agent_runs:write"],
        },
        secret="test-agent-secret",
    )

    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_capabilities": ["run_variant"], "run_mode": "plan_only"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Agent principal token missing exp"


def test_inactive_external_principal_token_is_rejected(client: TestClient):
    token = build_agent_principal_token(
        principal_id="revoked-agent",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:write"],
    )
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO principals (id, principal_type, tenant_id, status)
        VALUES (?, ?, ?, ?)
        """,
        ("revoked-agent", "external_agent", CLIENT_ID, "inactive"),
    )
    conn.commit()

    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_capabilities": ["run_variant"], "run_mode": "plan_only"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Agent principal is not active"


def test_bearer_token_cannot_self_assert_agent_profile(client: TestClient):
    token = build_agent_principal_token(
        principal_id="profileless-agent",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        scopes=["agent_runs:write"],
    )

    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "principal_type": "external_agent",
            "agent_profile_id": "self-asserted-profile",
            "allowed_capabilities": ["run_variant"],
            "run_mode": "plan_only",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "agent_profile_id does not match authenticated principal"


def _legacy_agent_principal_token(payload: dict, *, secret: str) -> str:
    payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"),
        payload_b64.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"
