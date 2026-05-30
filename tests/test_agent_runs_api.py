from __future__ import annotations

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
from application.services.agent_runtime.agent_first import list_skill_specs
from infrastructure.db.agent.agent_profiles import update_agent_profile_defaults
from infrastructure.db.agent.agent_registry import update_agent_registry_harness_profile
from shared.config.env import get_settings
from shared.db.connection import get_connection
from shared.db.connection import init_db, set_database_path

CLIENT_ID = "client-a"
USER_ID = "user-a"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    monkeypatch.setenv("ADMIN_USER_IDS", USER_ID)
    get_settings.cache_clear()
    monkeypatch.setattr(
        "api.utils.tenancy.settings.admin_user_ids",
        USER_ID,
    )
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


def _registry_params(**params):
    return {"client_id": CLIENT_ID, "user_id": USER_ID, **params}


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
    token = build_agent_principal_token(
        principal_id="principal-ext-1",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="external-buyer-assistant",
        scopes=["agent_runs:write", "agent_runs:read"],
    )
    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "client_id": CLIENT_ID,
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
    assert run["registry_version"] == "agent-runtime-static-v1"
    assert len(run["registry_fingerprint"]) == 64

    detail = client.get(
        f"/agent-runs/{run['id']}",
        headers={"Authorization": f"Bearer {token}"},
        params={"client_id": CLIENT_ID, "user_id": USER_ID},
    )
    assert detail.status_code == 200
    payload = detail.json()
    assert payload["run"]["trace_id"] == run["trace_id"]
    assert payload["run"]["registry_fingerprint"] == run["registry_fingerprint"]
    assert payload["actions"][0]["tool_id"] == "experiment.run_variant"
    assert payload["actions"][0]["skill_id"] == "optimize-product-representation"
    assert payload["actions"][0]["registry_version"] == "agent-runtime-static-v1"
    assert len(payload["actions"][0]["registry_fingerprint"]) == 64
    assert payload["actions"][0]["tool_version"] == "v1"
    assert payload["actions"][0]["skill_version"] == "v1"
    assert payload["actions"][0]["effect_class"] == "write_low_risk"

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        headers={"Authorization": f"Bearer {token}"},
        params={"client_id": CLIENT_ID, "user_id": USER_ID},
    )
    assert events.status_code == 200
    event_payload = events.json()
    assert event_payload["events"][0]["tool_id"] == "experiment.run_variant"
    assert event_payload["events"][0]["skill_id"] == "optimize-product-representation"
    assert event_payload["events"][0]["effect_class"] == "write_low_risk"


def test_create_agent_run_applies_agent_profile_harness_defaults(client: TestClient):
    token = build_agent_principal_token(
        principal_id="principal-ext-harness-default",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="external-buyer-assistant",
        scopes=["agent_runs:write"],
    )
    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "allowed_capabilities": ["run_variant"],
        },
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["harness_id"] == "safe_autonomy_b2b"
    assert run["run_mode"] == "auto_execute_safe"
    assert run["policy_profile_id"] == "safe_auto"


def test_create_agent_run_uses_persistent_agent_profile_defaults(client: TestClient):
    update_agent_profile_defaults(
        profile_id="buyer-assistant-v1",
        principal_id="external_agent:buyer-assistant-v1",
        principal_type="external_agent",
        name="Buyer Assistant v1",
        default_harness_id="operator_supervised",
        default_policy_profile_id="human_approval_required",
        risk_tier="operator_reviewed",
        channel_type="external_job_api",
    )
    token = build_agent_principal_token(
        principal_id="principal-ext-persisted-profile",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=["agent_runs:write"],
    )
    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_capabilities": ["run_variant"]},
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["agent_profile_id"] == "buyer-assistant-v1"
    assert run["harness_id"] == "operator_supervised"
    assert run["run_mode"] == "plan_only"
    assert run["policy_profile_id"] == "human_approval_required"


def test_create_agent_run_prefers_profile_policy_and_pins_tenant_registry(
    client: TestClient,
):
    update_agent_registry_harness_profile(
        profile_id="safe_autonomy_b2b",
        source="operator_override",
        profile={
            "id": "safe_autonomy_b2b",
            "name": "Safe Autonomy B2B",
            "description": "Allows a tenant-specific human-approval profile default.",
            "default_run_mode": "auto_execute_safe",
            "default_policy_profile_id": "safe_auto",
            "allowed_run_modes": ["auto_execute_safe"],
            "allowed_policy_profile_ids": ["safe_auto", "human_approval_required"],
            "planner_mode": "bounded_single_or_workflow",
            "retry_strategy": "last_safe_checkpoint",
            "fallback_order": ["registry_recovery_template"],
            "approval_strategy": "auto_low_risk_human_governed_high_risk",
            "memory_policy": "write_execution_receipts_and_learnings",
            "stopping_conditions": ["policy_block"],
        },
    )
    update_agent_profile_defaults(
        profile_id="buyer-assistant-v1",
        principal_id="external_agent:buyer-assistant-v1",
        principal_type="external_agent",
        name="Buyer Assistant v1 Tenant",
        tenant_id=CLIENT_ID,
        default_harness_id="safe_autonomy_b2b",
        default_policy_profile_id="human_approval_required",
        risk_tier="operator_reviewed",
        channel_type="external_job_api",
    )
    token = build_agent_principal_token(
        principal_id="principal-ext-tenant-profile",
        client_id=CLIENT_ID,
        principal_type="external_agent",
        agent_profile_id="buyer-assistant-v1",
        scopes=["agent_runs:write"],
    )
    response = client.post(
        "/agent-runs",
        headers={"Authorization": f"Bearer {token}"},
        json={"allowed_capabilities": ["run_variant"]},
    )

    assert response.status_code == 200
    run = response.json()["run"]
    assert run["policy_profile_id"] == "human_approval_required"
    registry_row = get_connection().execute(
        "SELECT payload_json FROM agent_registry_versions WHERE registry_fingerprint = ?",
        (run["registry_fingerprint"],),
    ).fetchone()
    assert registry_row is not None
    registry_payload = json.loads(registry_row["payload_json"])
    profile = next(
        item
        for item in registry_payload["agent_profile_defaults"]
        if item["id"] == "buyer-assistant-v1"
    )
    assert profile["tenant_id"] == CLIENT_ID
    assert profile["default_policy_profile_id"] == "human_approval_required"


def test_create_agent_run_rejects_unsupported_capability(client: TestClient):
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "allowed_capabilities": ["not_real"],
        },
    )
    assert response.status_code == 400
    assert "Unsupported allowed_capabilities: not_real" in response.json()["detail"]


def test_create_agent_run_rejects_unknown_profiles(client: TestClient):
    base = {"client_id": CLIENT_ID, "user_id": USER_ID, "allowed_capabilities": ["run_variant"]}
    bad_run_mode = client.post(
        "/agent-runs",
        json={**base, "run_mode": "manual"},
    )
    assert bad_run_mode.status_code == 400
    assert "Unsupported run_mode: manual" in bad_run_mode.json()["detail"]

    bad_policy = client.post(
        "/agent-runs",
        json={**base, "policy_profile_id": "unknown_profile"},
    )
    assert bad_policy.status_code == 400
    assert "Unsupported policy_profile_id: unknown_profile" in bad_policy.json()["detail"]

    bad_harness = client.post(
        "/agent-runs",
        json={**base, "harness_id": "pretend_harness"},
    )
    assert bad_harness.status_code == 400
    assert "Unsupported harness_id: pretend_harness" in bad_harness.json()["detail"]

    bad_harness_mode = client.post(
        "/agent-runs",
        json={
            **base,
            "harness_id": "safe_autonomy_b2b",
            "run_mode": "plan_only",
        },
    )
    assert bad_harness_mode.status_code == 400
    assert (
        "Harness 'safe_autonomy_b2b' does not allow run_mode: plan_only"
        in bad_harness_mode.json()["detail"]
    )


def test_create_agent_run_enforces_harness_effect_class_boundaries(client: TestClient):
    blocked = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "harness_id": "observe_only",
            "policy_profile_id": "observe",
            "allowed_capabilities": ["run_variant"],
        },
    )
    assert blocked.status_code == 400
    assert (
        "Harness 'observe_only' does not allow capability effect class: run_variant (write_low_risk)"
        in blocked.json()["detail"]
    )

    allowed = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "harness_id": "observe_only",
            "policy_profile_id": "observe",
            "allowed_capabilities": ["recommend_next_action"],
        },
    )
    assert allowed.status_code == 200
    run = allowed.json()["run"]
    assert run["harness_id"] == "observe_only"
    assert run["policy_profile_id"] == "observe"


def test_harness_planner_mode_filters_observe_only_plans(client: TestClient):
    update_agent_registry_harness_profile(
        profile_id="observe_only",
        source="operator_override",
        profile={
            "id": "observe_only",
            "name": "Observe Only",
            "description": "Test observe planner filtering with broad effects.",
            "default_run_mode": "plan_only",
            "default_policy_profile_id": "observe",
            "allowed_run_modes": ["plan_only"],
            "allowed_policy_profile_ids": ["observe"],
            "allowed_effect_classes": ["read", "recommend", "write_low_risk"],
            "planner_mode": "inspect_and_recommend",
            "retry_strategy": "none",
            "fallback_order": ["operator_chat"],
            "approval_strategy": "read_only",
            "memory_policy": "no_mutation",
            "stopping_conditions": ["recommendation_produced"],
        },
    )
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "harness_id": "observe_only",
            "policy_profile_id": "observe",
            "allowed_capabilities": ["run_variant", "recommend_next_action"],
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    actions = default_deps().agent_actions.list_agent_actions(
        agent_run_id=run["id"], limit=10
    )
    assert [action["capability_name"] for action in actions] == ["recommend_next_action"]


def test_harness_memory_policy_blocks_learning_mutation_plans(client: TestClient):
    update_agent_registry_harness_profile(
        profile_id="observe_only",
        source="operator_override",
        profile={
            "id": "observe_only",
            "name": "Observe Only",
            "description": "Test memory policy with broadened effects.",
            "default_run_mode": "plan_only",
            "default_policy_profile_id": "observe",
            "allowed_run_modes": ["plan_only"],
            "allowed_policy_profile_ids": ["observe"],
            "allowed_effect_classes": ["read", "recommend", "write_low_risk"],
            "planner_mode": "inspect_and_recommend",
            "retry_strategy": "none",
            "fallback_order": ["operator_chat"],
            "approval_strategy": "read_only",
            "memory_policy": "no_mutation",
            "stopping_conditions": ["recommendation_produced"],
        },
    )
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "harness_id": "observe_only",
            "policy_profile_id": "observe",
            "allowed_capabilities": ["update_posterior_and_decisions"],
        },
    )
    assert response.status_code == 400
    assert (
        "memory_policy forbids learning/memory mutation: update_posterior_and_decisions"
        in response.json()["detail"]
    )


def test_bounded_harness_planner_mode_caps_initial_actions(client: TestClient):
    response = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "harness_id": "safe_autonomy_b2b",
            "policy_profile_id": "safe_auto",
            "run_mode": "auto_execute_safe",
            "objective": {"max_initial_actions": 1},
            "allowed_capabilities": ["seed_hypotheses", "run_variant"],
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    actions = default_deps().agent_actions.list_agent_actions(
        agent_run_id=run["id"], limit=10
    )
    assert [action["capability_name"] for action in actions] == ["seed_hypotheses"]


def test_seed_skill_specs_are_available():
    skills = {skill.id for skill in list_skill_specs()}
    assert "discover-protocol-candidates" in skills
    assert "optimize-product-representation" in skills
    assert "request-validation-and-ingest-result" in skills


def test_operator_command_endpoint_records_receipt_and_delegates_approval(
    client: TestClient,
):
    created = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "allowed_capabilities": ["run_variant"],
        },
    )
    assert created.status_code == 200
    run = created.json()["run"]
    detail = client.get(
        f"/agent-runs/{run['id']}",
        params={"client_id": CLIENT_ID, "user_id": USER_ID},
    )
    action = detail.json()["actions"][0]

    response = client.post(
        f"/agent-runs/{run['id']}/commands",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "approve",
            "action_id": action["id"],
            "message": "Approve from operator chat.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["command"]["event_type"] == "operator_command_approve"
    assert payload["command"]["status"] == "received"
    assert payload["preflight"]["allowed"] is True
    assert payload["action"]["status"] == "approved"

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": CLIENT_ID, "user_id": USER_ID, "event_type": "all"},
    )
    event_types = [event["event_type"] for event in events.json()["events"]]
    assert "operator_command_approve" in event_types
    assert "action_approved" in event_types
    assert any(event["status"] == "completed" for event in events.json()["events"])


def test_operator_command_preflight_blocks_plan_only_step(client: TestClient):
    created = client.post(
        "/agent-runs",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "allowed_capabilities": ["run_variant"],
            "run_mode": "plan_only",
        },
    )
    assert created.status_code == 200
    run = created.json()["run"]

    response = client.post(
        f"/agent-runs/{run['id']}/commands/preflight",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "step",
        },
    )

    assert response.status_code == 200
    preflight = response.json()["preflight"]
    assert preflight["allowed"] is False
    assert preflight["risk_level"] == "medium"
    assert "Run is plan-only" in preflight["blockers"][0]


def test_operator_retry_command_creates_new_proposed_retry_action(client: TestClient):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["run_variant"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="variants_ready",
        status="failed",
    )
    failed = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="failed",
        capability_name="run_variant",
        capability_version="v1",
        inputs={"experiment_id": "exp-1", "variant_selection": "top_1"},
        outputs={},
        inputs_hash="inputs-1",
        outputs_hash=None,
        rationale="Original variant run failed.",
        confidence=0.55,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
        effect_class="write_low_risk",
        error="Transient execution failure.",
    )

    response = client.post(
        f"/agent-runs/{run['id']}/commands",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "retry",
            "action_id": failed["id"],
            "message": "Retry safely.",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    retry_action = payload["action"]
    assert payload["preflight"]["requires_confirmation"] is True
    assert retry_action["id"] != failed["id"]
    assert retry_action["status"] == "proposed"
    assert retry_action["retry_count"] == 1
    assert retry_action["dedupe_key"] == f"retry:{failed['id']}:same_action:1"
    assert retry_action["registry_version"] == "agent-runtime-static-v1"
    assert len(retry_action["registry_fingerprint"]) == 64
    assert retry_action["tool_version"] == "v1"
    assert retry_action["skill_version"] == "v1"
    assert deps.agent_actions.get_agent_action(failed["id"])["status"] == "failed"

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": CLIENT_ID, "user_id": USER_ID, "event_type": "all"},
    )
    event_types = [event["event_type"] for event in events.json()["events"]]
    assert "action_retry_proposed" in event_types
    assert "operator_command_retry" in event_types


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
        },
    )
    assert response.status_code == 200
    run = response.json()["run"]
    assert run["principal_type"] == "external_agent"
    assert run["principal_id"] == "principal-ext-2"
    assert run["agent_profile_id"] == "external-buyer-assistant"
    assert run["client_id"] == CLIENT_ID
    assert run["harness_id"] == "safe_autonomy_b2b"
    assert run["run_mode"] == "auto_execute_safe"

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
