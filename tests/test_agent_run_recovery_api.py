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
from shared.config.env import get_settings
from shared.db.connection import init_db, set_database_path

CLIENT_ID = "client-a"
USER_ID = "user-a"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    monkeypatch.setenv("ADMIN_USER_IDS", USER_ID)
    get_settings.cache_clear()
    monkeypatch.setattr("api.utils.tenancy.settings.admin_user_ids", USER_ID)
    db_path = tmp_path / "agent-run-recovery-api.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=CLIENT_ID, name="Client A")
    deps.clients.create_client(client_id="client-b", name="Client B")
    return TestClient(app)


def _create_failed_run(*, allowed_capabilities: list[str], **overrides) -> dict:
    deps = default_deps()
    return deps.agent_runs.create_agent_run(
        client_id=CLIENT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=allowed_capabilities,
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="failed",
        status="failed",
        **overrides,
    )


def _create_failed_variant_action(run_id: str) -> dict:
    deps = default_deps()
    return deps.agent_actions.create_agent_action(
        agent_run_id=run_id,
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


def _command_body(command_type: str, **extra) -> dict:
    return {
        "client_id": CLIENT_ID,
        "user_id": USER_ID,
        "command_type": command_type,
        **extra,
    }

def test_operator_retry_uses_harness_default_checkpoint_strategy(client: TestClient):
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
        harness_id="safe_autonomy_b2b",
        policy_profile_id="safe_auto",
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

    preflight_response = client.post(
        f"/agent-runs/{run['id']}/commands/preflight",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "retry",
            "action_id": failed["id"],
        },
    )

    assert preflight_response.status_code == 200
    preflight = preflight_response.json()["preflight"]
    assert preflight["recommended_retry_strategy"] == "last_safe_checkpoint"
    assert preflight["harness"]["harness_id"] == "safe_autonomy_b2b"
    assert "defaulted from harness" in preflight["warnings"][0]

    response = client.post(
        f"/agent-runs/{run['id']}/commands",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "retry",
            "action_id": failed["id"],
            "message": "Retry using harness default.",
        },
    )

    assert response.status_code == 200
    retry_action = response.json()["action"]
    assert retry_action["dedupe_key"] == f"retry:{failed['id']}:last_safe_checkpoint:1"
    assert retry_action["inputs"]["retry_from"] == "last_safe_checkpoint"
    assert retry_action["inputs"]["harness_retry_strategy"] == "last_safe_checkpoint"
    assert retry_action["inputs"]["recovery_context"]["harness"]["harness_id"] == (
        "safe_autonomy_b2b"
    )

    events = client.get(
        f"/agent-runs/{run['id']}/events",
        params={"client_id": CLIENT_ID, "user_id": USER_ID, "event_type": "all"},
    )
    retry_event = next(
        event
        for event in events.json()["events"]
        if event["event_type"] == "action_retry_proposed"
    )
    assert retry_event["anchors"]["retry_strategy"] == "last_safe_checkpoint"
    assert retry_event["anchors"]["harness_id"] == "safe_autonomy_b2b"


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
    assert action["inputs"]["recovery_context"]["template_id"] == (
        "recovery.recommend_next_action"
    )
    assert action["inputs"]["recovery_context"]["source_action_id"] == failed["id"]
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
    assert action["inputs"]["recovery_context"]["template_id"] == (
        "recovery.review_validation_readiness"
    )


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
    assert action["inputs"]["auto_run"] is False
    assert action["inputs"]["recovery_context"]["template_id"] == (
        "recovery.request_synthetic_validation"
    )
    assert "auto_run disabled" in action["rollback_guidance"]
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
    assert recovery_event["anchors"]["recovery_template_id"] == (
        "recovery.request_synthetic_validation"
    )


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
    assert action["inputs"]["recovery_context"]["template_id"] == (
        "recovery.recommend_next_action"
    )
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
    assert recovery_event["anchors"]["recovery_template_id"] == (
        "recovery.recommend_next_action"
    )
    assert "superseded by a later action" in recovery_event["anchors"][
        "rollback_guidance"
    ]


def test_change_plan_uses_harness_fallback_capability(client: TestClient):
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
        harness_id="safe_autonomy_b2b",
        policy_profile_id="safe_auto",
    )

    response = client.post(
        f"/agent-runs/{run['id']}/commands",
        json={
            "client_id": CLIENT_ID,
            "user_id": USER_ID,
            "command_type": "change_plan",
            "message": "Let the harness choose the safest recovery proposal.",
        },
    )

    assert response.status_code == 200
    action = response.json()["action"]
    assert action["capability_name"] == "review_validation_readiness"
    assert action["inputs"]["recovery_context"]["selection_reason"] == "harness_fallback"
    assert action["inputs"]["recovery_context"]["harness"]["fallback_order"] == [
        "registry_recovery_template",
        "operator_intervention",
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

