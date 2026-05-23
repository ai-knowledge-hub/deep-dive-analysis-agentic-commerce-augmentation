from __future__ import annotations

import sys
import types

import pytest

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
from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.commands.decisions import decide_agent_action
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
    NoApprovedActionError,
    PlanOnlyModeError,
    RunBusyError,
)
from shared.db.connection import get_connection, init_db, set_database_path


def _create_base_run(
    *,
    deps,
    run_mode: str = "auto_execute_safe",
    allowed_capabilities: list[str] | None = None,
    status: str = "planned",
    policy_profile_id: str | None = None,
) -> dict:
    deps.clients.create_client(client_id="client-a", name="Client A")
    return deps.agent_runs.create_agent_run(
        client_id="client-a",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=allowed_capabilities or ["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode=run_mode,
        state="battery_ready",
        status=status,
        policy_profile_id=policy_profile_id,
    )


def _add_approved_action(
    *,
    deps,
    run_id: str,
    capability_name: str = "freeze_retrieval_protocol",
    inputs: dict | None = None,
):
    return deps.agent_actions.create_agent_action(
        agent_run_id=run_id,
        sequence=1,
        status="approved",
        capability_name=capability_name,
        capability_version="v1",
        inputs=inputs or {"experiment_id": "exp-1"},
        outputs={},
        inputs_hash="in",
        outputs_hash=None,
        rationale="test action",
        confidence=0.8,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )


def test_step_once_rejects_plan_only_run(tmp_path):
    db_path = tmp_path / "agent-runtime-plan-only.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(deps=deps, run_mode="plan_only")
    _add_approved_action(deps=deps, run_id=run["id"])

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(PlanOnlyModeError):
        runtime.step_once(run_id=run["id"], user_id="user-a")


def test_step_once_executes_approved_action_and_updates_heartbeat(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "agent-runtime-step.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(deps=deps, run_mode="auto_execute_safe")
    action = _add_approved_action(deps=deps, run_id=run["id"])

    def _fake_execute_capability(**kwargs):
        assert kwargs["capability_name"] == "freeze_retrieval_protocol"
        return {"ok": True, "status": "done"}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        _fake_execute_capability,
    )

    runtime = AgentRuntimeService(deps=deps)
    result = runtime.step_once(run_id=run["id"], user_id="user-a")
    assert result.action is not None
    assert result.action["id"] == action["id"]
    assert result.action["status"] == "executed"
    assert result.action["outputs"]["ok"] is True

    updated = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert updated is not None
    assert updated["status"] in {"running", "planned", "completed"}
    assert updated["last_heartbeat_at"] is not None
    assert updated["lock_token"] is None


def test_step_once_fails_when_run_is_locked(tmp_path):
    db_path = tmp_path / "agent-runtime-busy.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(deps=deps, run_mode="auto_execute_safe")
    _add_approved_action(deps=deps, run_id=run["id"])
    deps.agent_runs.acquire_run_lock(
        run_id=run["id"], lock_token="external-lock", ttl_seconds=30
    )

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(RunBusyError):
        runtime.step_once(run_id=run["id"], user_id="user-a")


def test_step_once_rejects_paused_run(tmp_path):
    db_path = tmp_path / "agent-runtime-paused.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(
        deps=deps,
        run_mode="auto_execute_safe",
        status="paused",
    )
    _add_approved_action(deps=deps, run_id=run["id"])

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(AgentRuntimeError, match="not executable"):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    unchanged = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert unchanged is not None
    assert unchanged["status"] == "paused"


def test_step_once_rejects_safe_auto_external_side_effect(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-runtime-safe-auto-side-effect.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(
        deps=deps,
        run_mode="auto_execute_safe",
        allowed_capabilities=["request_synthetic_validation"],
        policy_profile_id="safe_auto",
    )
    action = _add_approved_action(
        deps=deps,
        run_id=run["id"],
        capability_name="request_synthetic_validation",
    )

    def _unexpected_execute_capability(**kwargs):
        raise AssertionError("policy should block before capability execution")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        _unexpected_execute_capability,
    )

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(AgentRuntimeError, match="forbids auto execution"):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert failed_action is not None
    assert failed_action["status"] == "failed"


def test_step_once_executes_read_only_protocol_adapter_and_records_receipt(tmp_path):
    db_path = tmp_path / "agent-runtime-protocol-adapter.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    deps.clients.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    deps.clients.create_product(
        product_id="product-a",
        brand_id="brand-a",
        name="Runner Pro",
        description="Daily running shoe.",
        metadata={
            "ucp": {"offer_url": "https://example.test/p/runner-pro"},
            "acp": {"offer_url": "https://example.test/p/runner-pro"},
        },
    )
    run = deps.agent_runs.create_agent_run(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        experiment_id=None,
        objective={},
        allowed_capabilities=["check_protocol_readiness"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="protocol_ready",
        status="planned",
        policy_profile_id="safe_auto",
    )
    action = _add_approved_action(
        deps=deps,
        run_id=run["id"],
        capability_name="check_protocol_readiness",
        inputs={"product_id": "product-a", "protocols": ["ucp", "acp"]},
    )

    runtime = AgentRuntimeService(deps=deps)
    result = runtime.step_once(run_id=run["id"], user_id="user-a")

    assert result.action is not None
    assert result.action["id"] == action["id"]
    outputs = result.action["outputs"]
    assert outputs["status"] == "protocol_readiness_checked"
    assert outputs["adapter"]["channel_type"] == "protocol"
    assert outputs["receipt_id"].startswith("receipt_")
    assert outputs["receipt"]["permission_scope"] == "protocol.readiness:read"
    assert outputs["receipt"]["risk"]["external_side_effects"] is False

    events = [
        event
        for event in deps.agent_events.list_agent_events(
            agent_run_id=run["id"],
            limit=10,
        )
        if event["event_type"] == "action_executed"
    ]
    assert len(events) == 1
    anchors = events[0]["anchors"]
    assert anchors["receipt_id"] == outputs["receipt_id"]
    assert anchors["adapter"]["adapter_id"] == "protocol.readiness.v1"
    assert anchors["receipt"]["channel_type"] == "protocol"


def test_step_once_executes_protocol_discovery_adapter_and_records_receipt(tmp_path):
    db_path = tmp_path / "agent-runtime-protocol-discovery-adapter.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    deps.clients.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    deps.clients.create_product(
        product_id="product-a",
        brand_id="brand-a",
        name="Runner Pro",
        description="Daily running shoe for road training.",
        metadata={
            "ucp": {
                "offer_url": "https://example.test/p/runner-pro",
                "price": 129.0,
                "availability": "in_stock",
            }
        },
    )
    run = deps.agent_runs.create_agent_run(
        client_id="client-a",
        brand_id="brand-a",
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["discover_protocol_candidates"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="protocol_discovery_ready",
        status="planned",
        policy_profile_id="safe_auto",
    )
    action = _add_approved_action(
        deps=deps,
        run_id=run["id"],
        capability_name="discover_protocol_candidates",
        inputs={"query": "running shoe", "protocol": "ucp", "limit": 5},
    )

    runtime = AgentRuntimeService(deps=deps)
    result = runtime.step_once(run_id=run["id"], user_id="user-a")

    assert result.action is not None
    assert result.action["id"] == action["id"]
    outputs = result.action["outputs"]
    assert outputs["status"] == "protocol_candidates_discovered"
    assert outputs["adapter"]["adapter_id"] == "protocol.discovery.v1"
    assert outputs["adapter"]["permission_scope"] == "protocol.discovery:read"
    assert outputs["receipt"]["risk"]["external_side_effects"] is False
    assert outputs["summary"]["count"] == 1
    assert outputs["candidates"][0]["id"] == "product-a"
    assert outputs["candidates"][0]["discovery_source"] == "ucp_local_metadata"
    assert outputs["summary"]["source_counts"] == {"ucp_local_metadata": 1}

    events = [
        event
        for event in deps.agent_events.list_agent_events(
            agent_run_id=run["id"],
            limit=10,
        )
        if event["event_type"] == "action_executed"
    ]
    assert len(events) == 1
    anchors = events[0]["anchors"]
    assert anchors["receipt_id"] == outputs["receipt_id"]
    assert anchors["adapter"]["adapter_id"] == "protocol.discovery.v1"
    assert anchors["receipt"]["evidence"]["candidate_ids"] == ["product-a"]
    assert anchors["receipt"]["evidence"]["source_counts"] == {
        "ucp_local_metadata": 1
    }


def test_step_once_marks_action_and_run_failed_on_capability_error(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "agent-runtime-fail.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(deps=deps, run_mode="auto_execute_safe")
    action = _add_approved_action(deps=deps, run_id=run["id"])

    def _raise_capability_error(**kwargs):
        raise CapabilityExecutionError("simulated failure")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        _raise_capability_error,
    )

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(CapabilityExecutionError):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert failed_action is not None
    assert failed_action["status"] == "failed"
    assert "simulated failure" in str(failed_action["error"])

    failed_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert "simulated failure" in str(failed_run["error"])
    assert failed_run["lock_token"] is None


def test_step_once_marks_policy_failure_on_invalid_registry_input(tmp_path):
    db_path = tmp_path / "agent-runtime-invalid-input.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(deps=deps, run_mode="auto_execute_safe")
    action = _add_approved_action(deps=deps, run_id=run["id"])
    conn = get_connection()
    conn.execute(
        "UPDATE agent_actions SET inputs_json = json(?) WHERE id = ?",
        ('{"experiment_id":"exp-1","retrieval_max_results":"five"}', action["id"]),
    )
    conn.commit()

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(AgentRuntimeError, match="retrieval_max_results"):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert failed_action is not None
    assert failed_action["status"] == "failed"
    assert "retrieval_max_results" in str(failed_action["error"])


def test_step_once_marks_failure_on_invalid_registry_output(tmp_path, monkeypatch):
    db_path = tmp_path / "agent-runtime-invalid-output.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(
        deps=deps,
        run_mode="auto_execute_safe",
        allowed_capabilities=["run_variant"],
    )
    action = _add_approved_action(
        deps=deps, run_id=run["id"], capability_name="run_variant"
    )

    def _fake_execute_capability(**kwargs):
        assert kwargs["capability_name"] == "run_variant"
        return {"metric_id": 123, "status": "done"}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        _fake_execute_capability,
    )

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(CapabilityExecutionError, match="metric_id"):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert failed_action is not None
    assert failed_action["status"] == "failed"
    assert "metric_id" in str(failed_action["error"])


def test_step_once_requires_approved_action(tmp_path):
    db_path = tmp_path / "agent-runtime-no-approved.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(deps=deps, run_mode="auto_execute_safe")

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(NoApprovedActionError):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    unchanged = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert unchanged is not None
    assert unchanged["status"] == "planned"
    assert unchanged["lock_token"] is None


def test_step_once_fails_unsupported_claimed_action_cleanly(tmp_path):
    db_path = tmp_path / "agent-runtime-unsupported-claimed-action.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    run = deps.agent_runs.create_agent_run(
        client_id="client-a",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=["registry_drift_capability"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="planned",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="approved",
        capability_name="registry_drift_capability",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash="in",
        outputs_hash=None,
        rationale="registry drift",
        confidence=0.8,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(AgentRuntimeError, match="Unsupported capability"):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert failed_action is not None
    assert failed_action["status"] == "failed"
    assert "Unsupported capability" in str(failed_action["error"])

    failed_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert failed_run is not None
    assert failed_run["status"] == "failed"
    assert failed_run["lock_token"] is None


def test_runtime_lifecycle_rejects_terminal_run_transitions(tmp_path):
    db_path = tmp_path / "agent-runtime-terminal-transitions.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(
        deps=deps,
        run_mode="auto_execute_safe",
        status="completed",
    )

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(AgentRuntimeError, match="Terminal runs cannot be started"):
        runtime.start_run(run_id=run["id"])
    with pytest.raises(AgentRuntimeError, match="Terminal runs cannot be paused"):
        runtime.pause_run(run_id=run["id"])
    with pytest.raises(AgentRuntimeError, match="already terminal"):
        runtime.cancel_run(run_id=run["id"])

    unchanged = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert unchanged is not None
    assert unchanged["status"] == "completed"


def test_runtime_rejects_unknown_run_mode(tmp_path):
    db_path = tmp_path / "agent-runtime-unknown-run-mode.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(
        deps=deps,
        run_mode="manual",
        status="planned",
    )
    _add_approved_action(deps=deps, run_id=run["id"])

    runtime = AgentRuntimeService(deps=deps)
    with pytest.raises(AgentRuntimeError, match="Unsupported run_mode"):
        runtime.start_run(run_id=run["id"])
    with pytest.raises(AgentRuntimeError, match="Unsupported run_mode"):
        runtime.step_once(run_id=run["id"], user_id="user-a")

    unchanged = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert unchanged is not None
    assert unchanged["status"] == "planned"


def test_decide_agent_action_rejects_high_risk_approval_under_safe_auto(tmp_path):
    db_path = tmp_path / "agent-runtime-high-risk-approval.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    run = _create_base_run(
        deps=deps,
        run_mode="auto_execute_safe",
        allowed_capabilities=["publish_copy_revision"],
        policy_profile_id="safe_auto",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="proposed",
        capability_name="publish_copy_revision",
        capability_version="v1",
        inputs={"experiment_id": "exp-1"},
        outputs={},
        inputs_hash="in",
        outputs_hash=None,
        rationale="high risk publish",
        confidence=0.8,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )

    with pytest.raises(ValueError, match="requires governed approval"):
        decide_agent_action(
            deps=deps,
            action_id=action["id"],
            client_id="client-a",
            user_id="user-a",
            decision="approve",
        )

    unchanged = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert unchanged is not None
    assert unchanged["status"] == "proposed"
