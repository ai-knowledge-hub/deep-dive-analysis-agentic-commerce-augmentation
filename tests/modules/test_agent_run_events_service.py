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
from application.services.agent_runtime.events import (
    list_agent_run_events,
    list_agent_run_events_page,
)
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
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action["id"],
        sequence=2,
        event_type="action_failed",
        status="failed",
        capability_name="run_variant",
        capability_version="v1",
        note="Action budget exceeded",
        is_policy_event=True,
        anchors={
            "experiment_id": None,
            "variant_id": None,
            "validation_job_id": None,
            "hypothesis_id": None,
            "snapshot_version": 3,
            "metric_id": "metric-123",
        },
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
    action_executed = deps.agent_actions.create_agent_action(
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
    action_failed = deps.agent_actions.create_agent_action(
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
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action_executed["id"],
        sequence=1,
        event_type="action_executed",
        status="executed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        note="ok",
        is_policy_event=False,
        anchors={},
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action_failed["id"],
        sequence=2,
        event_type="action_failed",
        status="failed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        note="Policy guardrail triggered",
        is_policy_event=True,
        anchors={},
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action_failed["id"],
        sequence=3,
        event_type="operator_command_retry",
        status="completed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        note="retry requested",
        is_policy_event=False,
        anchors={},
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
    command_events = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="command"
    )

    assert len(all_events) == 3
    assert len(failed_events) == 1
    assert failed_events[0]["status"] == "failed"
    assert len(policy_events) == 1
    assert policy_events[0]["is_policy_event"] is True
    assert len(executed_events) == 1
    assert executed_events[0]["status"] == "executed"
    assert len(command_events) == 1
    assert command_events[0]["event_type"] == "operator_command_retry"


def test_list_agent_run_events_page_supports_before_after_cursor(tmp_path):
    db_path = tmp_path / "agent-run-events-pagination.db"
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
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="running",
    )
    for idx in range(1, 6):
        action = deps.agent_actions.create_agent_action(
            agent_run_id=run["id"],
            sequence=idx,
            status="proposed",
            capability_name="freeze_retrieval_protocol",
            capability_version="v1",
            inputs={"idx": idx},
            outputs={},
            inputs_hash=f"in-{idx}",
            outputs_hash=f"out-{idx}",
            rationale=f"event {idx}",
            confidence=0.5,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
        )
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=action["id"],
            sequence=idx,
            event_type="action_proposed",
            status="proposed",
            capability_name="freeze_retrieval_protocol",
            capability_version="v1",
            note=f"event {idx}",
            is_policy_event=False,
            anchors={},
        )

    page_1 = list_agent_run_events_page(
        deps=deps,
        run_id=run["id"],
        limit=2,
        event_type="all",
    )
    assert len(page_1.events) == 2
    assert page_1.before_cursor
    assert page_1.after_cursor
    assert page_1.has_more_before is True
    assert page_1.has_more_after is False

    page_2 = list_agent_run_events_page(
        deps=deps,
        run_id=run["id"],
        limit=2,
        event_type="all",
        before=page_1.before_cursor,
    )
    assert len(page_2.events) == 2
    assert page_2.before_cursor
    assert page_2.after_cursor
    assert page_2.has_more_before is True
    assert page_2.has_more_after is True

    page_3 = list_agent_run_events_page(
        deps=deps,
        run_id=run["id"],
        limit=2,
        event_type="all",
        before=page_2.before_cursor,
    )
    assert len(page_3.events) == 1
    assert page_3.has_more_before is False
    assert page_3.has_more_after is True

    newer_from_page_2 = list_agent_run_events_page(
        deps=deps,
        run_id=run["id"],
        limit=2,
        event_type="all",
        after=page_2.after_cursor,
    )
    assert len(newer_from_page_2.events) >= 1
    assert newer_from_page_2.has_more_after is False

    all_ids = [event.id for event in page_1.events + page_2.events + page_3.events]
    assert len(all_ids) == 5
    assert len(set(all_ids)) == 5


def test_list_agent_run_events_supports_capability_status_and_time_filters(tmp_path):
    db_path = tmp_path / "agent-run-events-extra-filters.db"
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
        allowed_capabilities=["run_variant", "seed_hypotheses"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="running",
        status="running",
    )
    action_a = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="executed",
        capability_name="run_variant",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash="a-in",
        outputs_hash="a-out",
        rationale="a",
        confidence=0.7,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    action_b = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="failed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash="b-in",
        outputs_hash="b-out",
        rationale="b",
        confidence=0.3,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action_a["id"],
        sequence=1,
        event_type="action_executed",
        status="executed",
        capability_name="run_variant",
        capability_version="v1",
        note="a",
        is_policy_event=False,
        anchors={},
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action_b["id"],
        sequence=2,
        event_type="action_failed",
        status="failed",
        capability_name="seed_hypotheses",
        capability_version="v1",
        note="b",
        is_policy_event=False,
        anchors={},
    )

    by_status = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="all", status="failed"
    )
    by_capability = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="all", capability_name="run_variant"
    )
    by_since_future = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="all", since="2999-01-01 00:00:00"
    )
    by_until_past = list_agent_run_events(
        deps=deps, run_id=run["id"], event_type="all", until="2000-01-01 00:00:00"
    )

    assert len(by_status) == 1
    assert by_status[0]["status"] == "failed"
    assert len(by_capability) == 1
    assert by_capability[0]["capability_name"] == "run_variant"
    assert len(by_since_future) == 0
    assert len(by_until_past) == 0


def test_list_agent_run_events_page_can_center_by_event_id(tmp_path):
    db_path = tmp_path / "agent-run-events-center.db"
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
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="running",
    )
    event_ids: list[str] = []
    for idx in range(1, 8):
        action = deps.agent_actions.create_agent_action(
            agent_run_id=run["id"],
            sequence=idx,
            status="executed",
            capability_name="freeze_retrieval_protocol",
            capability_version="v1",
            inputs={},
            outputs={},
            inputs_hash=f"in-{idx}",
            outputs_hash=f"out-{idx}",
            rationale=f"e{idx}",
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
            event_type="action_executed",
            status="executed",
            capability_name="freeze_retrieval_protocol",
            capability_version="v1",
            note=f"event {idx}",
            is_policy_event=False,
            anchors={},
        )
        event_ids.append(str(event["id"]))

    anchor_id = event_ids[3]
    centered = list_agent_run_events_page(
        deps=deps,
        run_id=run["id"],
        event_type="all",
        event_id=anchor_id,
        around=5,
    )
    centered_ids = [event.id for event in centered.events]
    assert anchor_id in centered_ids
    assert len(centered_ids) <= 5
