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
