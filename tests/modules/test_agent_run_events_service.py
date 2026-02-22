from __future__ import annotations

import sys
import types

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
from application.services.agent_runtime.events import list_agent_run_events
from shared.db.connection import init_db, set_database_path


def test_list_agent_run_events_maps_action_anchors_and_policy_flags(tmp_path):
    db_path = tmp_path / "agent-run-events.db"
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
        allowed_capabilities=["run_variant"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="variants_ready",
        status="running",
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="failed",
        capability_name="run_variant",
        capability_version="v1",
        inputs={"experiment_id": "exp-1"},
        outputs={"new_metric_id": "metric-123"},
        inputs_hash="in",
        outputs_hash="out",
        rationale="try variant",
        confidence=0.6,
        snapshot_version=3,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        error="Action budget exceeded",
    )

    events = list_agent_run_events(deps=deps, run_id=run["id"], limit=20)
    assert len(events) == 1
    event = events[0]
    assert event["action_id"] == action["id"]
    assert event["event_type"] == "action_failed"
    assert event["is_policy_event"] is True
    anchors = event["anchors"]
    assert anchors["experiment_id"] is None
    assert anchors["variant_id"] is None
    assert anchors["validation_job_id"] is None
    assert anchors["hypothesis_id"] is None
    assert anchors["snapshot_version"] == 3
    assert anchors["metric_id"] == "metric-123"


def test_list_agent_run_events_supports_event_type_filters(tmp_path):
    db_path = tmp_path / "agent-run-events-filter.db"
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
        allowed_capabilities=["seed_hypotheses"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="hypotheses_ready",
        status="running",
    )
    deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="executed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        inputs={"experiment_id": "exp-1"},
        outputs={},
        inputs_hash="in",
        outputs_hash="out",
        rationale="ok",
        confidence=0.9,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="failed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        inputs={"experiment_id": "exp-1"},
        outputs={},
        inputs_hash="in2",
        outputs_hash="out2",
        rationale=None,
        confidence=0.2,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        error="Policy guardrail triggered",
    )

    all_events = list_agent_run_events(deps=deps, run_id=run["id"], event_type="all")
    failed_events = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="failed"
    )
    policy_events = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="policy"
    )
    executed_events = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="executed"
    )

    assert len(all_events) == 2
    assert len(failed_events) == 1
    assert failed_events[0]["status"] == "failed"
    assert len(policy_events) == 1
    assert policy_events[0]["is_policy_event"] is True
    assert len(executed_events) == 1
    assert executed_events[0]["status"] == "executed"
