from __future__ import annotations

import hashlib
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
from api.routes import agent_runs as agent_runs_route
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
    assert run["registry_version"] == "agent-runtime-static-v1"
    assert len(run["registry_fingerprint"]) == 64

    detail = client.get(
        f"/agent-runs/{run['id']}",
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
        params={"client_id": CLIENT_ID, "user_id": USER_ID},
    )
    assert events.status_code == 200
    event_payload = events.json()
    assert event_payload["events"][0]["tool_id"] == "experiment.run_variant"
    assert event_payload["events"][0]["skill_id"] == "optimize-product-representation"
    assert event_payload["events"][0]["effect_class"] == "write_low_risk"


def test_seed_skill_specs_are_available():
    skills = {skill.id for skill in list_skill_specs()}
    assert "discover-protocol-candidates" in skills
    assert "optimize-product-representation" in skills
    assert "request-validation-and-ingest-result" in skills


def test_agent_runtime_registry_endpoint_exposes_skills_tools_and_policies(
    client: TestClient,
):
    response = client.get("/agent-runs/registry")
    assert response.status_code == 200
    payload = response.json()
    assert payload["registry_version"] == "agent-runtime-static-v1"
    assert payload["registry_hash_algorithm"] == "sha256"
    assert len(payload["registry_fingerprint"]) == 64
    assert payload["registry_snapshot_id"] == payload["registry_fingerprint"]
    assert payload["registry_source"] == "static_code"
    assert payload["registry_status"] == "active"
    assert client.get("/agent-runs/registry").json()["registry_fingerprint"] == payload[
        "registry_fingerprint"
    ]
    row = get_connection().execute(
        """
        SELECT registry_version, registry_fingerprint, source, status, payload_json
        FROM agent_registry_versions
        WHERE registry_fingerprint = ?
        """,
        (payload["registry_fingerprint"],),
    ).fetchone()
    assert row is not None
    assert row["registry_version"] == "agent-runtime-static-v1"
    assert row["source"] == "static_code"
    assert row["status"] == "active"
    assert '"registry_version":"agent-runtime-static-v1"' in row["payload_json"].replace(" ", "")
    tool_ids = {tool["id"] for tool in payload["tools"]}
    skill_ids = {skill["id"] for skill in payload["skills"]}
    policy_ids = {profile["id"] for profile in payload["policy_profiles"]}

    assert "experiment.run_variant" in tool_ids
    assert "optimize-product-representation" in skill_ids
    assert "safe_auto" in policy_ids
    run_variant = next(
        capability
        for capability in payload["capabilities"]
        if capability["name"] == "run_variant"
    )
    assert run_variant["summary"]
    assert run_variant["input_schema"]["properties"]["experiment_id"]["type"] == "string"
    assert run_variant["output_schema"]["properties"]["metric_id"]["type"] == "string"
    assert "variant_id" in run_variant["output_schema"]["required"]
    assert run_variant["review_checklist"]
    assert run_variant["owner_principal_id"] == "platform.commerce-optimization"
    assert run_variant["steward_team"] == "commerce-optimization"
    assert payload["skill_ids_by_tool"]["experiment.run_variant"] == [
        "optimize-product-representation"
    ]
    assert payload["skill_ids_by_tool"]["run.read"] == ["triage-failed-run"]


def test_agent_runtime_registry_endpoint_audits_fingerprint_changes(
    client: TestClient, monkeypatch
):
    first = client.get("/agent-runs/registry").json()
    changed_contract = agent_runs_route.registry_contract_payload()
    changed_contract = {
        **changed_contract,
        "tools": [
            *changed_contract["tools"],
            {
                "id": "test.synthetic_tool",
                "capability_name": "synthetic_tool",
                "summary": "Synthetic test tool.",
                "default_version": "v-test",
            },
        ],
    }
    changed_fingerprint = hashlib.sha256(
        json.dumps(
            changed_contract,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()
    monkeypatch.setattr(
        agent_runs_route, "registry_contract_payload", lambda: changed_contract
    )
    monkeypatch.setattr(agent_runs_route, "registry_fingerprint", lambda: changed_fingerprint)

    changed = client.get("/agent-runs/registry").json()

    assert changed["registry_fingerprint"] == changed_fingerprint
    assert changed["registry_status"] == "active"
    row = get_connection().execute(
        """
        SELECT previous_registry_fingerprint, registry_fingerprint, diff_json
        FROM agent_registry_audit_events
        WHERE registry_fingerprint = ?
        """,
        (changed_fingerprint,),
    ).fetchone()
    assert row is not None
    assert row["previous_registry_fingerprint"] == first["registry_fingerprint"]
    diff = json.loads(row["diff_json"])
    assert diff["tools"]["added"] == ["test.synthetic_tool"]
    status_rows = get_connection().execute(
        """
        SELECT registry_fingerprint, status
        FROM agent_registry_versions
        WHERE registry_fingerprint IN (?, ?)
        """,
        (first["registry_fingerprint"], changed_fingerprint),
    ).fetchall()
    statuses = {item["registry_fingerprint"]: item["status"] for item in status_rows}
    assert statuses[first["registry_fingerprint"]] == "retired"
    assert statuses[changed_fingerprint] == "active"

    audit_response = client.get("/agent-runs/registry/audit", params={"limit": 5})
    assert audit_response.status_code == 200
    audit_payload = audit_response.json()
    assert audit_payload["events"][0]["registry_fingerprint"] == changed_fingerprint
    assert audit_payload["events"][0]["diff"]["tools"]["added"] == [
        "test.synthetic_tool"
    ]

    filtered_response = client.get(
        "/agent-runs/registry/audit",
        params={"registry_fingerprint": changed_fingerprint},
    )
    assert filtered_response.status_code == 200
    assert len(filtered_response.json()["events"]) == 1

    releases_response = client.get("/agent-runs/registry/releases")
    assert releases_response.status_code == 200
    releases = releases_response.json()["releases"]
    assert releases[0]["registry_fingerprint"] == changed_fingerprint
    assert releases[0]["status"] == "active"
    assert releases[0]["counts"]["tools"] == len(changed_contract["tools"])
    assert any(
        item["registry_fingerprint"] == first["registry_fingerprint"]
        and item["status"] == "retired"
        for item in releases
    )

    active_response = client.get(
        "/agent-runs/registry/releases",
        params={"status": "active"},
    )
    assert active_response.status_code == 200
    assert [item["status"] for item in active_response.json()["releases"]] == ["active"]

    invalid_status = client.get(
        "/agent-runs/registry/releases",
        params={"status": "draft"},
    )
    assert invalid_status.status_code == 400


def test_registry_pin_backfill_supports_dry_run_and_scoped_update(
    client: TestClient,
):
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
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="proposed",
        capability_name="run_variant",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale=None,
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )

    dry_run = client.post(
        "/agent-runs/registry/backfill-pins",
        json={"client_id": CLIENT_ID, "dry_run": True},
    )
    assert dry_run.status_code == 200
    dry_payload = dry_run.json()
    assert dry_payload["dry_run"] is True
    assert dry_payload["runs"]["matched"] == 1
    assert dry_payload["runs"]["updated"] == 0
    assert dry_payload["actions"]["matched"] == 1
    assert dry_payload["actions"]["updated"] == 0
    assert deps.agent_runs.get_agent_run(run_id=run["id"])["registry_fingerprint"] is None
    assert deps.agent_actions.get_agent_action(action["id"])["registry_fingerprint"] is None

    applied = client.post(
        "/agent-runs/registry/backfill-pins",
        json={"client_id": CLIENT_ID, "dry_run": False},
    )
    assert applied.status_code == 200
    applied_payload = applied.json()
    assert applied_payload["dry_run"] is False
    assert applied_payload["runs"]["updated"] == 1
    assert applied_payload["actions"]["updated"] == 1
    updated_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    updated_action = deps.agent_actions.get_agent_action(action["id"])
    assert updated_run["registry_version"] == "agent-runtime-static-v1"
    assert len(updated_run["registry_fingerprint"]) == 64
    assert updated_action["registry_version"] == "agent-runtime-static-v1"
    assert updated_action["registry_fingerprint"] == updated_run["registry_fingerprint"]
    assert updated_action["tool_id"] == "experiment.run_variant"
    assert updated_action["skill_id"] == "optimize-product-representation"
    assert updated_action["tool_version"] == "v1"
    assert updated_action["skill_version"] == "v1"
    audit = client.get("/agent-runs/registry/audit").json()["events"]
    backfill_event = next(
        item for item in audit if item["event_type"] == "registry_pin_backfill_applied"
    )
    assert backfill_event["source"] == "operator_backfill"
    assert backfill_event["registry_fingerprint"] == updated_run["registry_fingerprint"]
    assert backfill_event["diff"]["client_id"] == CLIENT_ID
    assert backfill_event["diff"]["runs"]["updated"] == 1
    assert backfill_event["diff"]["actions"]["updated"] == 1

    second_apply = client.post(
        "/agent-runs/registry/backfill-pins",
        json={"client_id": CLIENT_ID, "dry_run": False},
    )
    assert second_apply.status_code == 200
    assert second_apply.json()["runs"]["matched"] == 0
    assert second_apply.json()["actions"]["matched"] == 0


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


def test_retry_command_can_create_recovery_action_strategy(client: TestClient):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["run_variant", "recommend_next_action"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="failed",
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
            "metadata": {"retry_strategy": "create_recovery_action"},
        },
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["capability_name"] == "recommend_next_action"
    assert action["inputs"]["recovery_from_action_id"] == failed["id"]
    assert action["dedupe_key"] == f"retry:{failed['id']}:create_recovery_action:1"
    assert action["side_effects"] == ["create_experiment_recommendation"]
    assert "superseded by a later action" in action["rollback_guidance"]
    assert action["registry_version"] == "agent-runtime-static-v1"
    assert len(action["registry_fingerprint"]) == 64

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": CLIENT_ID, "user_id": USER_ID, "event_type": "all"},
    )
    assert "action_recovery_proposed" in [
        event["event_type"] for event in events.json()["events"]
    ]


def test_retry_recovery_action_can_target_allowed_capability(client: TestClient):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["run_variant", "review_validation_readiness"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="failed",
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
            "metadata": {
                "retry_strategy": "create_recovery_action",
                "capability_name": "review_validation_readiness",
            },
        },
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["capability_name"] == "review_validation_readiness"
    assert action["inputs"]["recovery_from_action_id"] == failed["id"]


def test_recovery_action_includes_compensating_recommendations_for_external_side_effect(
    client: TestClient,
):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=[
            "run_variant",
            "request_synthetic_validation",
            "review_validation_readiness",
            "recommend_next_action",
        ],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="failed",
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
            "metadata": {
                "retry_strategy": "create_recovery_action",
                "capability_name": "request_synthetic_validation",
            },
        },
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["capability_name"] == "request_synthetic_validation"
    assert action["effect_class"] == "external_side_effect"
    assert action["compensating_actions"][0]["capability_name"] == (
        "review_validation_readiness"
    )
    assert action["compensating_actions"][0]["priority"] == "high"

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": CLIENT_ID, "user_id": USER_ID, "event_type": "all"},
    )
    recovery_event = next(
        event
        for event in events.json()["events"]
        if event["event_type"] == "action_recovery_proposed"
    )
    assert recovery_event["anchors"]["compensating_actions"][0][
        "capability_name"
    ] == "review_validation_readiness"


def test_change_plan_command_creates_recovery_proposal(client: TestClient):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["recommend_next_action", "run_variant"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="failed",
        status="failed",
    )

    response = client.post(
        f"/agent-runs/{run['id']}/commands",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "change_plan",
            "message": "Create a recovery proposal from the failed run.",
            "metadata": {
                "inputs": {"experiment_id": "exp-1"},
                "recovery_strategy": "propose_next_action",
            },
        },
    )

    assert response.status_code == 200
    payload = response.json()
    action = payload["action"]
    assert action["status"] == "proposed"
    assert action["capability_name"] == "recommend_next_action"
    assert action["inputs"]["experiment_id"] == "exp-1"
    assert action["dedupe_key"].startswith("change_plan:")
    assert action["side_effects"] == ["create_experiment_recommendation"]
    assert "superseded by a later action" in action["rollback_guidance"]
    assert action["registry_version"] == "agent-runtime-static-v1"
    assert len(action["registry_fingerprint"]) == 64

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": CLIENT_ID, "user_id": USER_ID, "event_type": "all"},
    )
    event_types = [event["event_type"] for event in events.json()["events"]]
    assert "action_recovery_proposed" in event_types
    assert "operator_command_change_plan" in event_types
    recovery_event = next(
        event
        for event in events.json()["events"]
        if event["event_type"] == "action_recovery_proposed"
    )
    assert recovery_event["anchors"]["side_effects"] == [
        "create_experiment_recommendation"
    ]
    assert "superseded by a later action" in recovery_event["anchors"][
        "rollback_guidance"
    ]


def test_change_plan_preflight_blocks_unallowed_recovery_capability(
    client: TestClient,
):
    deps = default_deps()
    run = deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["recommend_next_action"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="failed",
        status="failed",
    )

    response = client.post(
        f"/agent-runs/{run['id']}/commands/preflight",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "change_plan",
            "metadata": {"capability_name": "run_variant"},
        },
    )

    assert response.status_code == 200
    preflight = response.json()["preflight"]
    assert preflight["allowed"] is False
    assert "not allowed" in preflight["blockers"][0]


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
