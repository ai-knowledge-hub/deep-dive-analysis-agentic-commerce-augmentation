from __future__ import annotations

import json
import shutil
import sqlite3

import pytest

from api.composition import default_deps
from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.registry import get_capability_spec
from application.services.agent_runtime.runtime.payloads import hash_payload
from shared.db.connection import set_database_path
from shared.db.migrations import MIGRATIONS_PATH, apply_migrations


def test_migration_045_upgrades_applied_044_and_quarantines_legacy_starts(tmp_path):
    old_migrations = tmp_path / "old-migrations"
    old_migrations.mkdir()
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        if migration.name <= "044_approval_effect_execution.sql":
            shutil.copy2(migration, old_migrations / migration.name)

    database_path = tmp_path / "applied-044.db"
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.executescript((MIGRATIONS_PATH.parent / "schema.sql").read_text())
    apply_migrations(conn, migrations_path=old_migrations)
    old_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(approval_effect_executions)"
        ).fetchall()
    }
    assert "authorization_snapshot_json" not in old_columns
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.executemany(
        """
        INSERT INTO approval_effect_executions (
            execution_id, tenant_id, workflow_id, action_id, approval_id,
            approval_envelope_digest, authorization_source_digest,
            effect_idempotency_key, status, error_code, started_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        tuple(
            (
                f"execution-legacy-{status}",
                "client-a",
                "run-legacy",
                f"action-legacy-{status}",
                f"approval-legacy-{status}",
                "a" * 64,
                "b" * 64,
                f"effect-legacy-{status}",
                status,
                "legacy_outcome_unknown" if status == "uncertain" else None,
                "2026-08-30T10:00:00.000000Z",
                "2026-08-30T10:00:01.000000Z",
            )
            for status in ("started", "uncertain")
        ),
    )
    conn.commit()

    apply_migrations(conn)

    upgraded_columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(approval_effect_executions)"
        ).fetchall()
    }
    assert {
        "authorization_snapshot_json",
        "authorization_snapshot_digest",
    } <= upgraded_columns
    validation_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(validation_jobs)").fetchall()
    }
    assert {
        "agent_action_id",
        "approval_id",
        "effect_idempotency_key",
        "approval_effect_execution_id",
        "requested_model",
    } <= validation_columns
    legacy = conn.execute(
        """
        SELECT authorization_snapshot_json, authorization_snapshot_digest
        FROM approval_effect_executions
        WHERE execution_id LIKE 'execution-legacy-%'
        """
    ).fetchall()
    assert [tuple(row) for row in legacy] == [(None, None), (None, None)]
    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        ("045_approval_effect_provenance.sql",),
    ).fetchone()
    conn.close()

    set_database_path(database_path)
    deps = default_deps()
    spec = get_capability_spec("request_synthetic_validation")
    assert spec is not None
    for status in ("started", "uncertain"):
        with pytest.raises(ApprovalAuthorizationError) as exc:
            reconcile_authorized_effect(
                deps=deps,
                run={"id": "run-legacy", "client_id": "client-a"},
                action={"id": f"action-legacy-{status}"},
                spec=spec,
                outputs={"validation_job_id": "job-legacy"},
                outputs_hash=hash_payload({"validation_job_id": "job-legacy"}),
                receipt_id="validation-job:job-legacy",
            )
        assert exc.value.code == "effect_start_evidence_unavailable"


def test_migration_046_upgrades_applied_045_from_immutable_effect_start(tmp_path):
    old_migrations = tmp_path / "old-migrations"
    old_migrations.mkdir()
    for migration in sorted(MIGRATIONS_PATH.glob("*.sql")):
        if migration.name <= "045_approval_effect_provenance.sql":
            shutil.copy2(migration, old_migrations / migration.name)

    database_path = tmp_path / "applied-045.db"
    conn = sqlite3.connect(database_path)
    conn.row_factory = sqlite3.Row
    conn.executescript((MIGRATIONS_PATH.parent / "schema.sql").read_text())
    apply_migrations(conn, migrations_path=old_migrations)
    assert "requested_model" not in {
        row["name"]
        for row in conn.execute("PRAGMA table_info(validation_jobs)").fetchall()
    }
    conn.execute("PRAGMA foreign_keys = OFF")
    snapshot = {
        "executable_inputs": {
            "experiment_id": "experiment-a",
            "model": "approved-model",
        }
    }
    conn.execute(
        """
        INSERT INTO approval_effect_executions (
            execution_id, tenant_id, workflow_id, action_id, approval_id,
            approval_envelope_digest, authorization_source_digest,
            effect_idempotency_key, status, started_at, updated_at,
            authorization_snapshot_json, authorization_snapshot_digest
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'started', ?, ?, json(?), ?)
        """,
        (
            "execution-existing",
            "client-a",
            "run-existing",
            "action-existing",
            "approval-existing",
            "a" * 64,
            "b" * 64,
            "effect-existing",
            "2026-08-31T10:00:00.000000Z",
            "2026-08-31T10:00:01.000000Z",
            json.dumps(snapshot),
            "c" * 64,
        ),
    )
    conn.execute(
        """
        INSERT INTO validation_jobs (
            id, client_id, entity_type, entity_id, provider, mode, model,
            prompt_version, status, agent_action_id, approval_id,
            effect_idempotency_key, approval_effect_execution_id,
            input_payload_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            "job-existing",
            "client-a",
            "experiment_run",
            "experiment-a",
            "openrouter",
            "in_app_byok",
            "substituted-expensive-model",
            "v1",
            "completed",
            "action-existing",
            "approval-existing",
            "effect-existing",
            "execution-existing",
            json.dumps({"source": "pre-046"}),
        ),
    )
    conn.commit()

    apply_migrations(conn)

    upgraded = conn.execute(
        "SELECT model, requested_model FROM validation_jobs WHERE id = ?",
        ("job-existing",),
    ).fetchone()
    assert tuple(upgraded) == (
        "substituted-expensive-model",
        "approved-model",
    )
    assert conn.execute(
        "SELECT 1 FROM schema_migrations WHERE name = ?",
        ("046_approval_validation_requested_model.sql",),
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError, match="requested model are immutable"):
        conn.execute(
            "UPDATE validation_jobs SET requested_model = ? WHERE id = ?",
            ("substituted-expensive-model", "job-existing"),
        )
    conn.rollback()
    conn.close()
