from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest

from api.composition import default_deps
from application.services.agent_runtime.scheduler import AgentRuntimeSchedulerService
from application.services.workflow_compatibility import (
    project_sequential_run_best_effort,
)
from domain.workflow.sequential_compatibility import (
    SequentialCompatibilityError,
    compile_sequential_workflow,
)
from infrastructure.db.core.connection import get_connection


TENANT_ID = "tenant-compatibility"


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _seed_sequential_run(tmp_path):
    deps = default_deps()
    deps.set_database_path(tmp_path / "sequential-workflow.db")
    deps.init_db()
    deps.clients.create_client(client_id=TENANT_ID, name="Compatibility tenant")
    run = deps.agent_runs.create_agent_run(
        client_id=TENANT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"goal": "Improve product discovery"},
        allowed_capabilities=["freeze_retrieval_protocol", "create_hypothesis"],
        capability_versions={},
        budgets={"max_actions": 2},
        approval_policy={"mode": "exact"},
        requires_approval=True,
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:planner",
        agent_profile_id="commerce-optimizer",
        harness_id="harness.default",
        policy_profile_id="policy.plan-only",
        idempotency_key="compatibility-run-a",
        trace_id="trace-compatibility-a",
        registry_version="registry-v1",
        registry_fingerprint="f" * 64,
    )
    actions = []
    for sequence, capability in enumerate(
        ("freeze_retrieval_protocol", "create_hypothesis"), start=1
    ):
        inputs = {"sequence": sequence}
        action = deps.agent_actions.create_agent_action(
            agent_run_id=run["id"],
            sequence=sequence,
            status="proposed",
            capability_name=capability,
            capability_version="v1",
            inputs=inputs,
            outputs={},
            inputs_hash=_digest(inputs),
            outputs_hash=None,
            rationale="Compatibility test",
            confidence=0.9,
            snapshot_version=None,
            hypothesis_id=None,
            variant_id=None,
            validation_job_id=None,
            tool_id=f"tool.{capability}",
            skill_id=f"skill.{capability}",
            registry_version="registry-v1",
            registry_fingerprint="f" * 64,
            tool_version="v1",
            skill_version="v1",
            effect_class="recommend",
        )
        actions.append(action)
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=action["id"],
            sequence=sequence,
            event_type="action_proposed",
            status="proposed",
            capability_name=capability,
            capability_version="v1",
            principal_type="internal_agent",
            principal_id="internal-agent:planner",
            tool_id=action["tool_id"],
            skill_id=action["skill_id"],
            effect_class="recommend",
            trace_id="trace-compatibility-a",
            anchors={"inputs_hash": action["inputs_hash"]},
        )
    return deps, run, actions


def _seed_single_action_run(deps, *, tenant_id: str, suffix: str):
    if tenant_id != TENANT_ID:
        deps.clients.create_client(client_id=tenant_id, name=f"Tenant {suffix}")
    run = deps.agent_runs.create_agent_run(
        client_id=tenant_id,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"goal": f"Goal {suffix}"},
        allowed_capabilities=["freeze_retrieval_protocol"],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id=f"internal-agent:{suffix}",
        agent_profile_id=None,
        harness_id="harness.default",
        policy_profile_id="policy.plan-only",
        trace_id=f"trace-{suffix}",
        registry_version="registry-v1",
        registry_fingerprint="f" * 64,
    )
    inputs = {"suffix": suffix}
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status="proposed",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        inputs=inputs,
        outputs={},
        inputs_hash=_digest(inputs),
        outputs_hash=None,
        rationale="Compatibility test",
        confidence=0.9,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="tool.freeze",
        skill_id="skill.freeze",
        registry_version="registry-v1",
        registry_fingerprint="f" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class="recommend",
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=action["id"],
        sequence=1,
        event_type="action_proposed",
        status="proposed",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        principal_type="internal_agent",
        principal_id=f"internal-agent:{suffix}",
        trace_id=f"trace-{suffix}",
    )
    return run, action


def test_projection_persists_exact_revision_membership_and_linear_graph(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)

    result = deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID,
        run_id=run["id"],
    )
    projection = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID,
        run_id=run["id"],
    )

    assert result["outcome"] == "current"
    assert result["operation"] == "created"
    assert projection is not None
    assert projection["structure_and_event_ids_current"] is True
    assert projection["governed_semantic_parity"] == "not_projected_slice_7a"
    assert "equivalent" not in projection
    assert projection["revision"]["revision"] == 1
    assert [task["task_id"] for task in projection["tasks"]] == [
        action["id"] for action in actions
    ]
    assert [task["sequence"] for task in projection["tasks"]] == [1, 2]
    assert [task["capability_version"] for task in projection["tasks"]] == [
        "v1",
        "v1",
    ]
    assert len(projection["edges"]) == 1
    assert projection["edges"][0]["from_task_id"] == actions[0]["id"]
    assert projection["edges"][0]["to_task_id"] == actions[1]["id"]
    assert {event["trace_id"] for event in projection["events"]} == {
        "trace-compatibility-a"
    }


def test_projection_replay_and_restart_are_idempotent(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    first = deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    restarted = default_deps()
    restarted.set_database_path(tmp_path / "sequential-workflow.db")
    restarted.init_db()

    second = restarted.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    projection = restarted.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run["id"]
    )

    assert second["operation"] == "replayed"
    assert second["imported_events"] == 0
    assert second["structural_digest"] == first["structural_digest"]
    assert projection is not None
    assert len(projection["tasks"]) == 2
    assert len(projection["events"]) == 2


def test_lifecycle_changes_are_read_from_live_compatibility_views(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )

    deps.agent_actions.update_agent_action_status(
        action_id=actions[0]["id"], status="approved"
    )
    deps.agent_runs.update_agent_run(run_id=run["id"], status="running")
    projection = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run["id"]
    )

    assert projection is not None
    assert projection["run_projection"]["status"] == "running"
    assert projection["tasks"][0]["status"] == "approved"
    assert projection["workflow"]["initial_status"] == "planned"
    assert projection["tasks"][0]["initial_status"] == "proposed"


def test_new_source_event_marks_read_stale_until_idempotent_import(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=actions[0]["id"],
        sequence=1,
        event_type="action_approved",
        status="approved",
        principal_type="user",
        principal_id="operator-a",
        trace_id="trace-compatibility-a",
    )

    stale = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    assert stale is not None
    assert stale["structure_and_event_ids_current"] is False

    refreshed = deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    current = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    assert refreshed["imported_events"] == 1
    assert current is not None
    assert current["structure_and_event_ids_current"] is True


def test_replay_rejects_mutated_source_event_identity(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    conn = get_connection()
    conn.execute(
        "UPDATE agent_events SET principal_id = 'tampered-principal' WHERE agent_run_id = ?",
        (run["id"],),
    )
    conn.commit()

    with pytest.raises(ValueError, match="disagrees with its source"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id=TENANT_ID, run_id=run["id"]
        )


def test_new_action_is_detected_as_revision_drift_not_silently_added(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    inputs = {"sequence": 3}
    deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=3,
        status="proposed",
        capability_name="review_validation_readiness",
        capability_version="v1",
        inputs=inputs,
        outputs={},
        inputs_hash=_digest(inputs),
        outputs_hash=None,
        rationale="Late action",
        confidence=0.8,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="tool.review",
        skill_id="skill.review",
        registry_version="registry-v1",
        registry_fingerprint="f" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class="recommend",
    )

    result = deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    projection = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run["id"]
    )

    assert result["outcome"] == "drifted"
    assert result["error_code"] == "structural_drift"
    assert projection is not None
    assert len(projection["tasks"]) == 2
    assert projection["projection_status"]["source_action_count"] == 3
    assert projection["projection_status"]["projected_task_count"] == 2
    assert projection["structure_and_event_ids_current"] is False


def test_tenant_scope_and_immutable_structure_fail_closed(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.clients.create_client(client_id="other-tenant", name="Other tenant")
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )

    assert (
        deps.workflow_compatibility.get_sequential_projection(
            tenant_id="other-tenant", run_id=run["id"]
        )
        is None
    )
    with pytest.raises(ValueError, match="tenant scope"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id="other-tenant", run_id=run["id"]
        )
    conn = get_connection()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute(
            """
            UPDATE workflow_compatibility_tasks SET task_key = 'tampered'
            WHERE workflow_id = ?
            """,
            (run["id"],),
        )
    conn.rollback()


def test_projection_rejects_cross_tenant_lineage(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.clients.create_client(client_id="other-tenant", name="Other tenant")
    other = deps.agent_runs.create_agent_run(
        client_id="other-tenant",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={},
        allowed_capabilities=[],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=True,
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:other",
        agent_profile_id=None,
        harness_id="harness.default",
        policy_profile_id="policy.plan-only",
        trace_id="trace-other",
        registry_version="registry-v1",
        registry_fingerprint="f" * 64,
    )
    conn = get_connection()
    conn.execute(
        "UPDATE agent_runs SET parent_run_id = ? WHERE id = ?",
        (other["id"], run["id"]),
    )
    conn.commit()

    with pytest.raises(ValueError, match="lineage leaves the tenant scope"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id=TENANT_ID, run_id=run["id"]
        )


@pytest.mark.parametrize(
    ("other_tenant", "suffix"),
    ((TENANT_ID, "same-tenant-other-run"), ("tenant-b", "cross-tenant-run")),
)
def test_projection_rejects_cross_run_action_events(tmp_path, other_tenant, suffix):
    deps, run, _ = _seed_sequential_run(tmp_path)
    _, other_action = _seed_single_action_run(
        deps,
        tenant_id=other_tenant,
        suffix=suffix,
    )
    deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=other_action["id"],
        sequence=3,
        event_type="action_approved",
        status="approved",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        principal_type="user",
        principal_id="operator-a",
        trace_id="trace-compatibility-a",
    )

    with pytest.raises(ValueError, match="event action does not belong"):
        deps.workflow_compatibility.project_sequential_run(
            tenant_id=TENANT_ID, run_id=run["id"]
        )


def test_event_insert_guard_rejects_cross_run_action_reference(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    _, other_action = _seed_single_action_run(
        deps,
        tenant_id=TENANT_ID,
        suffix="database-guard",
    )
    source = deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=other_action["id"],
        sequence=3,
        event_type="action_approved",
        status="approved",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        principal_type="user",
        principal_id="operator-a",
        trace_id="trace-compatibility-a",
    )
    conn = get_connection()
    source_row = conn.execute(
        "SELECT rowid AS source_row_order FROM agent_events WHERE id = ?",
        (source["id"],),
    ).fetchone()
    assert source_row is not None
    payload = {
        "source_event_id": source["id"],
        "source_sequence": 3,
        "source_status": "approved",
        "capability_name": "freeze_retrieval_protocol",
        "capability_version": "v1",
        "tool_id": None,
        "skill_id": None,
        "effect_class": None,
        "anchors": {},
        "note": "",
        "is_policy_event": False,
    }
    payload_json = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )

    with pytest.raises(sqlite3.IntegrityError, match="source event is invalid"):
        conn.execute(
            """
            INSERT INTO workflow_compatibility_events (
                event_id, tenant_id, workflow_id, sequence, source_event_id,
                source_row_order, event_type, event_version, entity_type,
                entity_id, principal_id, command_id, event_index, payload_json,
                payload_hash, causation_id, correlation_id, trace_id,
                occurred_at, recorded_at
            ) VALUES (?, ?, ?, 2, ?, ?, ?, '1.0', 'task', ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?)
            """,
            (
                f"workflow-event:{source['id']}",
                TENANT_ID,
                run["id"],
                source["id"],
                int(source_row["source_row_order"]),
                "compatibility.agent.action_approved",
                other_action["id"],
                "operator-a",
                f"compatibility-import:{run['id']}",
                int(source_row["source_row_order"]),
                payload_json,
                _digest(payload),
                source["id"],
                "trace-compatibility-a",
                "trace-compatibility-a",
                source["timestamp"],
                source["timestamp"],
            ),
        )
    conn.rollback()


def test_edges_are_revision_scoped_and_exactly_compared(tmp_path):
    deps, run_a, actions_a = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run_a["id"]
    )
    run_b, action_b = _seed_single_action_run(deps, tenant_id="tenant-b", suffix="b")
    deps.workflow_compatibility.project_sequential_run(
        tenant_id="tenant-b", run_id=run_b["id"]
    )
    conn = get_connection()

    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        conn.execute(
            """
            INSERT INTO workflow_compatibility_edges (
                edge_id, tenant_id, workflow_id, revision, from_task_id,
                to_task_id, join_policy
            ) VALUES ('cross-tenant-edge', ?, ?, 1, ?, ?, 'all')
            """,
            (TENANT_ID, run_a["id"], action_b["id"], actions_a[0]["id"]),
        )
    conn.rollback()

    conn.execute(
        """
        INSERT INTO workflow_compatibility_edges (
            edge_id, tenant_id, workflow_id, revision, from_task_id,
            to_task_id, join_policy
        ) VALUES ('unexpected-reverse-edge', ?, ?, 1, ?, ?, 'all')
        """,
        (TENANT_ID, run_a["id"], actions_a[1]["id"], actions_a[0]["id"]),
    )
    conn.commit()
    projection = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run_a["id"]
    )
    assert projection is not None
    assert projection["structure_and_event_ids_current"] is False


def test_insert_or_replace_cannot_rewrite_imported_event(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    conn = get_connection()
    row = conn.execute(
        """
        SELECT * FROM workflow_compatibility_events
        WHERE tenant_id = ? AND workflow_id = ?
        ORDER BY sequence ASC LIMIT 1
        """,
        (TENANT_ID, run["id"]),
    ).fetchone()
    assert row is not None
    columns = list(row.keys())
    values = dict(row)
    values["payload_json"] = "{}"
    values["payload_hash"] = _digest({})
    placeholders = ", ".join("?" for _ in columns)
    with pytest.raises(sqlite3.IntegrityError, match="already exists"):
        conn.execute(
            f"INSERT OR REPLACE INTO workflow_compatibility_events "
            f"({', '.join(columns)}) VALUES ({placeholders})",
            tuple(values[column] for column in columns),
        )
    conn.rollback()
    preserved = conn.execute(
        "SELECT payload_json FROM workflow_compatibility_events WHERE event_id = ?",
        (row["event_id"],),
    ).fetchone()
    assert preserved is not None
    assert preserved["payload_json"] == row["payload_json"]


def test_first_event_insert_must_match_canonical_source_content(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    source = deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=actions[0]["id"],
        sequence=1,
        event_type="action_approved",
        status="approved",
        principal_type="user",
        principal_id="operator-a",
        trace_id="trace-compatibility-a",
    )
    conn = get_connection()
    source_row = conn.execute(
        "SELECT rowid AS source_row_order FROM agent_events WHERE id = ?",
        (source["id"],),
    ).fetchone()
    assert source_row is not None

    with pytest.raises(sqlite3.IntegrityError, match="source event is invalid"):
        conn.execute(
            """
            INSERT INTO workflow_compatibility_events (
                event_id, tenant_id, workflow_id, sequence, source_event_id,
                source_row_order, event_type, event_version, entity_type,
                entity_id, principal_id, command_id, event_index, payload_json,
                payload_hash, causation_id, correlation_id, trace_id,
                occurred_at, recorded_at
            ) VALUES (?, ?, ?, 2, ?, ?, ?, '1.0', 'task', ?, ?, ?, ?,
                      json('{}'), ?, ?, ?, ?, ?, ?)
            """,
            (
                f"workflow-event:{source['id']}",
                TENANT_ID,
                run["id"],
                source["id"],
                int(source_row["source_row_order"]),
                "compatibility.agent.action_approved",
                actions[0]["id"],
                "operator-a",
                f"compatibility-import:{run['id']}",
                int(source_row["source_row_order"]),
                _digest({}),
                source["id"],
                "trace-compatibility-a",
                "trace-compatibility-a",
                source["timestamp"],
                source["timestamp"],
            ),
        )
    conn.rollback()


def test_scheduler_backfills_and_retries_failed_projection(tmp_path):
    deps, run, _ = _seed_sequential_run(tmp_path)
    assert (
        deps.workflow_compatibility.get_sequential_projection(
            tenant_id=TENANT_ID, run_id=run["id"]
        )
        is None
    )
    scheduler = AgentRuntimeSchedulerService(deps=deps)

    first = scheduler.run_once(
        client_id=TENANT_ID,
        max_runs_per_client=1,
        max_steps_per_run=1,
        max_projection_repairs_per_client=1,
    )
    assert first["workflow_projection_reconciliation"][0]["runs_considered"] == 1
    projection = deps.workflow_compatibility.get_sequential_projection(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    assert projection is not None
    assert projection["structure_and_event_ids_current"] is True

    deps.workflow_compatibility.record_projection_failure(
        tenant_id=TENANT_ID,
        run_id=run["id"],
        error_code="transient_failure",
    )
    second = scheduler.run_once(
        client_id=TENANT_ID,
        max_runs_per_client=1,
        max_steps_per_run=1,
        max_projection_repairs_per_client=1,
    )
    result = second["workflow_projection_reconciliation"][0]["results"][0]
    assert result["outcome"] == "current"


def test_best_effort_projection_failure_never_raises_into_runtime():
    class BrokenStore:
        def project_sequential_run(self, **_kwargs):
            raise RuntimeError("projection unavailable")

        def record_projection_failure(self, **kwargs):
            return {"outcome": "failed", **kwargs}

    result = project_sequential_run_best_effort(
        store=BrokenStore(),
        tenant_id=TENANT_ID,
        run_id="run-a",
    )

    assert result == {
        "outcome": "failed",
        "tenant_id": TENANT_ID,
        "run_id": "run-a",
        "error_code": "RuntimeError",
    }


def test_compiler_rejects_non_gap_sequence_and_hostile_primitive_subclasses():
    class LyingString(str):
        def strip(self, *_args, **_kwargs):
            return "trusted"

    run = {
        "id": LyingString(" untrusted "),
        "client_id": TENANT_ID,
    }
    with pytest.raises(SequentialCompatibilityError, match="canonical string"):
        compile_sequential_workflow(run=run, actions=[], events=[])
