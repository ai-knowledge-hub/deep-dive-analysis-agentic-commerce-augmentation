from __future__ import annotations

import shutil
import sqlite3

from shared.db.migrations import MIGRATIONS_PATH, apply_migrations


def test_migration_050_upgrades_an_applied_049_database_without_old_writer_breakage(
    tmp_path,
):
    old_migrations = tmp_path / "old-migrations"
    old_migrations.mkdir()
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        if migration.name <= "049_governed_receipt_writer_compatibility.sql":
            shutil.copy2(migration, old_migrations / migration.name)

    database_path = tmp_path / "applied-049.db"
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((MIGRATIONS_PATH.parent / "schema.sql").read_text())
    apply_migrations(conn, migrations_path=old_migrations)
    conn.execute("INSERT INTO clients (id, name) VALUES ('tenant-a', 'Tenant A')")
    conn.execute(
        """
        INSERT INTO agent_runs (
            id, client_id, objective_json, allowed_capabilities_json,
            capability_versions_json, budgets_json, approval_policy_json,
            requires_approval, state, status, run_mode
        ) VALUES (
            'workflow-a', 'tenant-a', '{}', '[]', '{}', '{}', '{}',
            0, 'planned', 'planned', 'observe'
        )
        """
    )
    conn.commit()
    assert (
        conn.execute(
            """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'workflow_outcome_commands'
        """
        ).fetchone()
        is None
    )

    apply_migrations(conn)

    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        ("050_workflow_outcome_ledger.sql",),
    ).fetchone()
    assert conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'workflow_completion_decisions'
        """
    ).fetchone()
    assert (
        conn.execute(
            "SELECT status FROM agent_runs WHERE id = 'workflow-a'"
        ).fetchone()["status"]
        == "planned"
    )

    apply_migrations(conn, migrations_path=old_migrations)
    assert (
        conn.execute(
            "SELECT status FROM agent_runs WHERE id = 'workflow-a'"
        ).fetchone()["status"]
        == "planned"
    )
    conn.close()


def test_migration_051_upgrades_an_applied_050_database_without_legacy_run_breakage(
    tmp_path,
):
    old_migrations = tmp_path / "old-migrations-050"
    old_migrations.mkdir()
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        if migration.name <= "050_workflow_outcome_ledger.sql":
            shutil.copy2(migration, old_migrations / migration.name)

    database_path = tmp_path / "applied-050.db"
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((MIGRATIONS_PATH.parent / "schema.sql").read_text())
    apply_migrations(conn, migrations_path=old_migrations)
    conn.execute("INSERT INTO clients (id, name) VALUES ('tenant-a', 'Tenant A')")
    conn.execute(
        """
        INSERT INTO agent_runs (
            id, client_id, objective_json, allowed_capabilities_json,
            capability_versions_json, budgets_json, approval_policy_json,
            requires_approval, state, status, run_mode
        ) VALUES (
            'workflow-a', 'tenant-a', '{}', '[]', '{}', '{}', '{}',
            0, 'planned', 'planned', 'observe'
        )
        """
    )
    conn.execute(
        """
        INSERT INTO workflow_outcome_commands (
            command_id, tenant_id, workflow_id, command_type, principal_id,
            authority_source, authority_version, idempotency_key, request_hash,
            artifact_type, artifact_id, artifact_digest, issued_at, completed_at
        ) VALUES (
            'publish-a', 'tenant-a', 'workflow-a',
            'publish_completion_contract', 'policy:publisher', 'host-policy',
            'v1', 'idem:publish-a', ?, 'completion_contract', 'criteria-a', ?,
            '2026-09-12T09:00:00.000000Z', '2026-09-12T09:00:00.000000Z'
        )
        """,
        ("b" * 64, "a" * 64),
    )
    conn.execute(
        """
        INSERT INTO workflow_completion_criteria (
            criteria_digest, criteria_id, criteria_version, tenant_id,
            workflow_id, graph_revision, objective_id, authority_hash,
            payload_json, created_at, command_id
        ) VALUES (
            ?, 'criteria-a', 'v1', 'tenant-a', 'workflow-a', 1,
            'objective-a', ?, '{}', '2026-09-12T09:00:00.000000Z', 'publish-a'
        )
        """,
        ("a" * 64, "c" * 64),
    )
    conn.commit()

    apply_migrations(conn)

    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        ("051_workflow_completion_lifecycle.sql",),
    ).fetchone()
    assert (
        conn.execute(
            "SELECT status FROM agent_runs WHERE id = 'workflow-a'"
        ).fetchone()["status"]
        == "planned"
    )
    assert conn.execute(
        """
        SELECT 1 FROM sqlite_master
        WHERE type = 'table' AND name = 'workflow_completion_projections'
        """
    ).fetchone()
    conn.execute("UPDATE agent_runs SET status = 'completed' WHERE id = 'workflow-a'")
    conn.commit()
    assert (
        conn.execute(
            "SELECT status FROM agent_runs WHERE id = 'workflow-a'"
        ).fetchone()["status"]
        == "completed"
    )
    conn.close()


def test_migration_052_upgrades_an_applied_051_database(tmp_path):
    old_migrations = tmp_path / "old-migrations-051"
    old_migrations.mkdir()
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        if migration.name <= "051_workflow_completion_lifecycle.sql":
            shutil.copy2(migration, old_migrations / migration.name)

    database_path = tmp_path / "applied-051.db"
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript((MIGRATIONS_PATH.parent / "schema.sql").read_text())
    apply_migrations(conn, migrations_path=old_migrations)

    assert (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("workflow_completion_projection_repairs",),
        ).fetchone()
        is None
    )

    apply_migrations(conn)

    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        ("052_completion_projection_repair.sql",),
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        ("workflow_completion_projection_repairs",),
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        ("workflow_completion_projection_decision_guard_update",),
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        ("completion_projection_repairs_guard_insert",),
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        ("completion_projection_repair_audits_no_delete",),
    ).fetchone()
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'trigger' AND name = ?",
        ("completion_projection_repair_audits_no_replace",),
    ).fetchone()
    conn.close()
