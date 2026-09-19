from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import shutil
import sqlite3

import pytest

from api.composition import default_deps
from infrastructure.db.agent.approval_persistence import (
    insert_agent_audit_event_locked,
)
from infrastructure.db.core.connection import get_connection
from shared.db.connection import _workflow_compatibility_event_payload
from shared.db.migrations import MIGRATIONS_PATH, apply_migrations
from tests.modules.test_sequential_workflow_compatibility import (
    TENANT_ID,
    _seed_single_action_run,
    _seed_sequential_run,
)


def _projected_event(conn, source_event_id: str):
    return conn.execute(
        "SELECT * FROM workflow_compatibility_events WHERE source_event_id = ?",
        (source_event_id,),
    ).fetchone()


def test_migration_055_preserves_pre_slice_7c_old_writer_compatibility(tmp_path):
    old_migrations = tmp_path / "old-migrations-054"
    old_migrations.mkdir()
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        if migration.name <= "054_workflow_governed_semantic_compatibility.sql":
            shutil.copy2(migration, old_migrations / migration.name)

    conn = sqlite3.connect(tmp_path / "applied-054.db")
    conn.row_factory = sqlite3.Row
    conn.create_function(
        "workflow_sha256",
        1,
        lambda value: hashlib.sha256(str(value).encode()).hexdigest(),
        deterministic=True,
    )
    conn.create_function(
        "workflow_compatibility_event_payload",
        11,
        _workflow_compatibility_event_payload,
        deterministic=True,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((MIGRATIONS_PATH.parent / "schema.sql").read_text())
    apply_migrations(conn, migrations_path=old_migrations)
    conn.execute("INSERT INTO clients (id, name) VALUES ('tenant-old', 'Old writer')")
    conn.execute(
        """
        INSERT INTO agent_runs (
            id, client_id, objective_json, allowed_capabilities_json,
            capability_versions_json, budgets_json, approval_policy_json,
            requires_approval, state, status, run_mode
        ) VALUES (
            'workflow-old', 'tenant-old', '{}', '[]', '{}', '{}', '{}',
            0, 'planned', 'planned', 'observe'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, sequence, event_type, status
        ) VALUES ('event-before-055', 'workflow-old', 0, 'legacy', 'planned')
        """
    )
    conn.commit()

    apply_migrations(conn)

    row = conn.execute(
        """
        SELECT workflow_event_projection_required FROM agent_runs
        WHERE id = 'workflow-old'
        """
    ).fetchone()
    assert row["workflow_event_projection_required"] == 0
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, sequence, event_type, status
        ) VALUES ('event-after-055', 'workflow-old', 1, 'legacy', 'planned')
        """
    )
    conn.commit()
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE agent_run_id = 'workflow-old'"
        ).fetchone()[0]
        == 2
    )
    conn.close()


def test_current_writer_fails_closed_until_the_shadow_exists(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_runs SET workflow_event_projection_required = 1
        WHERE id = ?
        """,
        (run["id"],),
    )
    conn.commit()
    before = conn.execute(
        "SELECT COUNT(*) FROM agent_events WHERE agent_run_id = ?", (run["id"],)
    ).fetchone()[0]

    with pytest.raises(sqlite3.IntegrityError, match="shadow is required"):
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=actions[0]["id"],
            sequence=7,
            event_type="premature_event",
            status="approved",
            principal_id="operator-a",
        )

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE agent_run_id = ?", (run["id"],)
        ).fetchone()[0]
        == before
    )
    with pytest.raises(sqlite3.IntegrityError, match="agent run is immutable"):
        deps.agent_runs.delete_agent_run(run_id=run["id"], client_id=TENANT_ID)
    assert deps.agent_runs.get_agent_run(run_id=run["id"]) is not None


def test_event_and_exact_compatibility_projection_commit_together(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )

    event = deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=actions[0]["id"],
        sequence=7,
        event_type="dual_write_verified",
        status="approved",
        capability_name="freeze_retrieval_protocol",
        capability_version="v1",
        principal_type="user",
        principal_id="operator-a",
        tool_id="tool.freeze",
        skill_id="skill.freeze",
        effect_class="recommend",
        trace_id="trace-compatibility-a",
        note="exact projection",
        is_policy_event=True,
        anchors={"approval_id": "approval-a"},
    )

    projected = _projected_event(get_connection(), event["id"])
    assert projected is not None
    expected_payload = {
        "source_event_id": event["id"],
        "source_sequence": 7,
        "source_status": "approved",
        "capability_name": "freeze_retrieval_protocol",
        "capability_version": "v1",
        "tool_id": "tool.freeze",
        "skill_id": "skill.freeze",
        "effect_class": "recommend",
        "anchors": {"approval_id": "approval-a"},
        "note": "exact projection",
        "is_policy_event": True,
    }
    payload_json = json.dumps(
        expected_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    assert projected["event_id"] == f"workflow-event:{event['id']}"
    assert projected["tenant_id"] == TENANT_ID
    assert projected["workflow_id"] == run["id"]
    assert projected["entity_id"] == actions[0]["id"]
    assert projected["payload_json"] == payload_json
    assert (
        projected["payload_hash"] == hashlib.sha256(payload_json.encode()).hexdigest()
    )
    assert projected["occurred_at"] == event["timestamp"]
    status = (
        get_connection()
        .execute(
            """
        SELECT projection_state, source_event_count, projected_event_count
        FROM workflow_compatibility_projection_status
        WHERE tenant_id = ? AND workflow_id = ?
        """,
            (TENANT_ID, run["id"]),
        )
        .fetchone()
    )
    assert status["projection_state"] == "current"
    assert status["source_event_count"] == status["projected_event_count"]


def test_projection_failure_rolls_back_the_source_event(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    conn = get_connection()
    conn.execute(
        """
        CREATE TEMP TRIGGER fail_dual_write
        BEFORE INSERT ON workflow_compatibility_events
        WHEN NEW.event_type = 'compatibility.agent.fault_injected'
        BEGIN SELECT RAISE(ABORT, 'injected projection failure'); END
        """
    )

    with pytest.raises(sqlite3.IntegrityError, match="injected projection failure"):
        deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=actions[0]["id"],
            sequence=8,
            event_type="fault_injected",
            status="failed",
            principal_id="operator-a",
            trace_id="trace-compatibility-a",
        )

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE event_type = 'fault_injected'"
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            """
        SELECT COUNT(*) FROM workflow_compatibility_events
        WHERE event_type = 'compatibility.agent.fault_injected'
        """
        ).fetchone()[0]
        == 0
    )


def test_outer_transaction_rollback_removes_both_event_rows(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    conn = get_connection()
    event_id = "transaction-rollback-event"
    conn.execute("BEGIN IMMEDIATE")
    insert_agent_audit_event_locked(
        conn,
        workflow_id=run["id"],
        action_id=actions[0]["id"],
        event={
            "id": event_id,
            "sequence": 9,
            "event_type": "outer_transaction_event",
            "status": "approved",
            "principal_id": "operator-a",
            "trace_id": "trace-compatibility-a",
        },
    )
    assert _projected_event(conn, event_id) is not None
    conn.rollback()

    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE id = ?", (event_id,)
        ).fetchone()[0]
        == 0
    )
    assert _projected_event(conn, event_id) is None


def test_concurrent_writers_allocate_gap_free_projection_order(tmp_path):
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    before = (
        get_connection()
        .execute(
            """
        SELECT COUNT(*) FROM workflow_compatibility_events
        WHERE tenant_id = ? AND workflow_id = ?
        """,
            (TENANT_ID, run["id"]),
        )
        .fetchone()[0]
    )

    def write_event(index: int):
        return deps.agent_events.create_agent_event(
            agent_run_id=run["id"],
            action_id=actions[index % len(actions)]["id"],
            sequence=20 + index,
            event_type=f"concurrent_event_{index}",
            status="approved",
            principal_id="operator-a",
            trace_id="trace-compatibility-a",
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        events = list(pool.map(write_event, range(2)))

    rows = (
        get_connection()
        .execute(
            """
        SELECT projected.sequence, projected.source_row_order,
               source.rowid AS source_rowid
        FROM workflow_compatibility_events projected
        JOIN agent_events source ON source.id = projected.source_event_id
        WHERE projected.source_event_id IN (?, ?)
        ORDER BY projected.sequence
        """,
            (events[0]["id"], events[1]["id"]),
        )
        .fetchall()
    )
    assert [row["sequence"] for row in rows] == [before, before + 1]
    assert all(row["source_row_order"] == row["source_rowid"] for row in rows)


def test_restart_replay_does_not_duplicate_dual_written_events(tmp_path):
    database_path = tmp_path / "sequential-workflow.db"
    deps, run, actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    event = deps.agent_events.create_agent_event(
        agent_run_id=run["id"],
        action_id=actions[0]["id"],
        sequence=30,
        event_type="restart_event",
        status="approved",
        principal_id="operator-a",
        trace_id="trace-compatibility-a",
    )

    restarted = default_deps()
    restarted.set_database_path(database_path)
    restarted.init_db()
    replay = restarted.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    assert replay["imported_events"] == 0
    assert (
        get_connection()
        .execute(
            """
        SELECT COUNT(*) FROM workflow_compatibility_events
        WHERE source_event_id = ?
        """,
            (event["id"],),
        )
        .fetchone()[0]
        == 1
    )


def test_projected_source_and_shadow_are_immutable_against_coordinated_rewrite(
    tmp_path,
):
    deps, run, _ = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    conn = get_connection()
    source = conn.execute(
        "SELECT id, note_text FROM agent_events WHERE agent_run_id = ? LIMIT 1",
        (run["id"],),
    ).fetchone()
    projected = _projected_event(conn, source["id"])
    assert projected is not None

    with pytest.raises(sqlite3.IntegrityError, match="fence is permanent"):
        conn.execute(
            """
            UPDATE agent_runs SET workflow_event_projection_required = 0
            WHERE id = ?
            """,
            (run["id"],),
        )
    conn.rollback()
    fence = conn.execute(
        """
        SELECT workflow_event_projection_required FROM agent_runs WHERE id = ?
        """,
        (run["id"],),
    ).fetchone()
    assert fence["workflow_event_projection_required"] == 1

    with pytest.raises(sqlite3.IntegrityError, match="agent event is immutable"):
        conn.execute(
            "UPDATE agent_events SET note_text = 'coordinated rewrite' WHERE id = ?",
            (source["id"],),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="agent event is immutable"):
        conn.execute("DELETE FROM agent_events WHERE id = ?", (source["id"],))
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="identity already exists"):
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_events (
                id, agent_run_id, action_id, sequence, event_type, status,
                anchors_json
            ) VALUES (?, ?, NULL, 0, 'rewritten', 'failed', json('{}'))
            """,
            (source["id"], run["id"]),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="workflow event is immutable"):
        conn.execute(
            """
            UPDATE workflow_compatibility_events
            SET payload_json = json('{}')
            WHERE source_event_id = ?
            """,
            (source["id"],),
        )
    conn.rollback()

    preserved_source = conn.execute(
        "SELECT note_text FROM agent_events WHERE id = ?", (source["id"],)
    ).fetchone()
    preserved_projection = _projected_event(conn, source["id"])
    assert preserved_source["note_text"] == source["note_text"]
    assert preserved_projection["payload_json"] == projected["payload_json"]


def test_unfenced_event_cannot_be_reassigned_into_a_fenced_run(tmp_path):
    deps, fenced_run, fenced_actions = _seed_sequential_run(tmp_path)
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=fenced_run["id"]
    )
    legacy_run, legacy_action = _seed_single_action_run(
        deps, tenant_id=TENANT_ID, suffix="legacy-reassignment"
    )
    conn = get_connection()
    legacy_event = conn.execute(
        """
        SELECT id, agent_run_id, action_id FROM agent_events
        WHERE agent_run_id = ?
        """,
        (legacy_run["id"],),
    ).fetchone()
    before = conn.execute(
        """
        SELECT source_event_count, projected_event_count, projection_state
        FROM workflow_compatibility_projection_status
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (TENANT_ID, fenced_run["id"]),
    ).fetchone()

    with pytest.raises(sqlite3.IntegrityError, match="agent event is immutable"):
        conn.execute(
            """
            UPDATE agent_events
            SET agent_run_id = ?, action_id = ?
            WHERE id = ?
            """,
            (fenced_run["id"], fenced_actions[0]["id"], legacy_event["id"]),
        )
    conn.rollback()

    preserved = conn.execute(
        "SELECT agent_run_id, action_id FROM agent_events WHERE id = ?",
        (legacy_event["id"],),
    ).fetchone()
    after = conn.execute(
        """
        SELECT source_event_count, projected_event_count, projection_state
        FROM workflow_compatibility_projection_status
        WHERE tenant_id = ? AND workflow_id = ?
        """,
        (TENANT_ID, fenced_run["id"]),
    ).fetchone()
    assert preserved["agent_run_id"] == legacy_run["id"]
    assert preserved["action_id"] == legacy_action["id"]
    assert dict(after) == dict(before)
    assert after["source_event_count"] == after["projected_event_count"]
    assert after["projection_state"] == "current"


def test_shadowed_run_cannot_be_deleted_or_replaced_before_its_first_event(tmp_path):
    deps, _, _ = _seed_sequential_run(tmp_path)
    run, action = _seed_single_action_run(
        deps, tenant_id=TENANT_ID, suffix="zero-event-shadow"
    )
    conn = get_connection()
    conn.execute("DELETE FROM agent_events WHERE agent_run_id = ?", (run["id"],))
    conn.commit()
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE agent_run_id = ?", (run["id"],)
        ).fetchone()[0]
        == 0
    )

    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=run["id"]
    )
    assert (
        conn.execute(
            """
            SELECT COUNT(*) FROM workflow_compatibility_events
            WHERE workflow_id = ?
            """,
            (run["id"],),
        ).fetchone()[0]
        == 0
    )
    assert (
        conn.execute(
            """
            SELECT COUNT(*) FROM workflow_compatibility_runs
            WHERE source_agent_run_id = ?
            """,
            (run["id"],),
        ).fetchone()[0]
        == 1
    )
    # Prove the run guards independently consult the shadow instead of trusting
    # only the fence. This simulates a database corrupted before the monotonic
    # fence guard was installed.
    conn.execute("DROP TRIGGER workflow_event_projection_fence_no_downgrade")
    conn.execute(
        """
        UPDATE agent_runs SET workflow_event_projection_required = 0
        WHERE id = ?
        """,
        (run["id"],),
    )
    conn.commit()

    with pytest.raises(sqlite3.IntegrityError, match="agent run is immutable"):
        deps.agent_runs.delete_agent_run(run_id=run["id"], client_id=TENANT_ID)

    with pytest.raises(sqlite3.IntegrityError, match="identity already exists"):
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_runs
            SELECT * FROM agent_runs WHERE id = ?
            """,
            (run["id"],),
        )
    conn.rollback()

    assert deps.agent_runs.get_agent_run(run_id=run["id"]) is not None
    assert deps.agent_actions.get_agent_action(action_id=action["id"]) is not None
    assert (
        conn.execute(
            """
            SELECT COUNT(*) FROM workflow_compatibility_runs
            WHERE source_agent_run_id = ?
            """,
            (run["id"],),
        ).fetchone()[0]
        == 1
    )


def test_unfenced_run_cannot_adopt_an_identity_retained_by_a_shadow(tmp_path):
    deps, _, _ = _seed_sequential_run(tmp_path)
    shadowed_run, _ = _seed_single_action_run(
        deps, tenant_id=TENANT_ID, suffix="orphaned-shadow-identity"
    )
    candidate_run, _ = _seed_single_action_run(
        deps, tenant_id=TENANT_ID, suffix="identity-candidate"
    )
    conn = get_connection()
    for run_id in (shadowed_run["id"], candidate_run["id"]):
        conn.execute("DELETE FROM agent_events WHERE agent_run_id = ?", (run_id,))
        conn.execute("DELETE FROM agent_actions WHERE agent_run_id = ?", (run_id,))
    conn.commit()
    deps.workflow_compatibility.project_sequential_run(
        tenant_id=TENANT_ID, run_id=shadowed_run["id"]
    )

    # Model a database orphaned before the source-delete guard was installed.
    # The identity-update guard must consult NEW.id rather than only OLD scope.
    conn.execute("DROP TRIGGER projected_agent_runs_no_delete")
    conn.execute("DELETE FROM agent_runs WHERE id = ?", (shadowed_run["id"],))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError, match="identity and tenant"):
        conn.execute(
            "UPDATE agent_runs SET id = ? WHERE id = ?",
            (shadowed_run["id"], candidate_run["id"]),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="identity already exists"):
        conn.execute(
            """
            INSERT INTO agent_runs (
                id, client_id, objective_json, allowed_capabilities_json,
                capability_versions_json, budgets_json, approval_policy_json,
                requires_approval, state, status, run_mode, principal_type,
                principal_id, workflow_event_projection_required
            ) VALUES (
                ?, ?, json('{}'), json('[]'), json('{}'), json('{}'), json('{}'),
                0, 'planned', 'planned', 'observe', 'internal_agent',
                'replacement-principal', 0
            )
            """,
            (shadowed_run["id"], TENANT_ID),
        )
    conn.rollback()

    assert deps.agent_runs.get_agent_run(run_id=candidate_run["id"]) is not None
    assert deps.agent_runs.get_agent_run(run_id=shadowed_run["id"]) is None
    assert (
        conn.execute(
            """
            SELECT COUNT(*) FROM workflow_compatibility_runs
            WHERE source_agent_run_id = ?
            """,
            (shadowed_run["id"],),
        ).fetchone()[0]
        == 1
    )
