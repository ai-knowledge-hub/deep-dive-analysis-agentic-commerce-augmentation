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
from application.services.agent_runtime.agent_first import list_skill_specs
from shared.config.env import get_settings
from shared.db.connection import get_connection
from shared.db.connection import init_db, set_database_path

CLIENT_ID = "client-a"
USER_ID = "user-a"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    get_settings.cache_clear()
    db_path = tmp_path / "agent-runs-api.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=CLIENT_ID, name="Client A")
    deps.clients.create_client(client_id="client-b", name="Client B")
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


def test_agent_run_routes_enforce_client_scope(client: TestClient):
    run, events = _seed_run_with_events()
    action_id = events[0]["action_id"]

    wrong_scope_run = client.get(
        f"/agent-runs/{run['id']}",
        params={"client_id": "client-b", "user_id": USER_ID},
    )
    assert wrong_scope_run.status_code == 404

    wrong_scope_events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": "client-b", "user_id": USER_ID},
    )
    assert wrong_scope_events.status_code == 404

    wrong_scope_decision = client.post(
        f"/agent-runs/actions/{action_id}/decision",
        json={"client_id": "client-b", "user_id": USER_ID, "decision": "approve"},
    )
    assert wrong_scope_decision.status_code == 404


def test_create_agent_run_persists_principal_policy_and_trace_fields(client: TestClient):
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "principal_type": "external_agent",
            "principal_id": "principal-ext-1",
            "agent_profile_id": "external-buyer-assistant",
            "harness_id": "safe_autonomy_b2b",
            "policy_profile_id": "safe_auto",
            "idempotency_key": "req-123",
            "allowed_capabilities": ["run_variant"],
            "run_mode": "auto_execute_safe",
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["principal_type"] == "external_agent"
    assert run["principal_id"] == "principal-ext-1"
    assert run["agent_profile_id"] == "external-buyer-assistant"
    assert run["harness_id"] == "safe_autonomy_b2b"
    assert run["policy_profile_id"] == "safe_auto"
    assert run["idempotency_key"] == "req-123"
    assert str(run["trace_id"]).startswith("trace_")

    detail = client.get(
        f"/agent-runs/{run['id']}",
        params={"client_id": CLIENT_ID, "user_id": USER_ID},
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["run"]["trace_id"] == run["trace_id"]
    assert payload["actions"][0]["tool_id"] == "experiment.run_variant"
    assert payload["actions"][0]["effect_class"] == "write_low_risk"


def test_seed_skill_specs_are_available():
    skills = {skill.id for skill in list_skill_specs()}
    assert "discover-protocol-candidates" in skills
    assert "optimize-product-representation" in skills
    assert "request-validation-and-ingest-result" in skills


def test_create_agent_run_resolves_machine_principal_from_bearer_token(
    client: TestClient,
):
    token = build_agent_principal_token(
        principal_id="principal-ext-2",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="external-buyer-assistant",
        scopes=["agent_runs:write"],
    )
    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "allowed_capabilities": ["seed_hypotheses"],
            "run_mode": "plan_only",
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["principal_type"] == "external_agent"
    assert run["principal_id"] == "principal-ext-2"
    assert run["agent_profile_id"] == "external-buyer-assistant"
    assert run["client_id"] == CLIENT_ID

    principal_row = get_connection().execute(
        "SELECT * FROM principals WHERE id = ?",
        ("principal-ext-2",),
    ).fetchone()
    assert principal_row is not None
    assert principal_row["principal_type"] == "external_agent"
    assert principal_row["tenant_id"] == CLIENT_ID


def test_create_agent_run_rejects_client_scope_mismatch_for_machine_principal(
    client: TestClient,
):
    token = build_agent_principal_token(
        principal_id="principal-ext-3",
        client_id=CLIENT_ID,
        principal_type="external_agent",
    )
    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "client_id": "client-b",
            "allowed_capabilities": ["seed_hypotheses"],
        },
    )
    assert response.status_code == 403


def test_create_agent_run_human_path_uses_namespaced_principal_id(client: TestClient):
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "allowed_capabilities": ["seed_hypotheses"],
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["principal_type"] == "human"
    assert run["principal_id"] == f"human:{USER_ID}"
