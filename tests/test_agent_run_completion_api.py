from __future__ import annotations

import sys
import types
import sqlite3
from datetime import timedelta

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
from api.utils.principals import build_agent_principal_token, ensure_principal
from infrastructure.db.core.connection import get_connection
from infrastructure.db.workflow.outcome_rows import OutcomeLedgerDataError
from shared.config.env import get_settings
from shared.db.migrations import MIGRATIONS_PATH
from tests.modules.test_workflow_completion_lifecycle import _commit, _prepare_snapshot
from tests.modules.workflow_outcome_ledger_support import (
    NOW,
    command,
    create_workflow,
    with_outcome_ledger,
)


TENANT_ID = "tenant-a"
OPERATOR_ID = "human:completion-operator"


@pytest.fixture
def completion_api(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_PRINCIPAL_SIGNING_SECRET", "test-agent-secret")
    get_settings.cache_clear()
    deps = default_deps()
    deps.set_database_path(tmp_path / "completion-projection-api.db")
    deps.init_db()
    outcome_deps = with_outcome_ledger(deps)
    return TestClient(app), outcome_deps


def _operator_headers(*, principal_id=OPERATOR_ID, scopes=None, tenant_id=TENANT_ID):
    token = build_agent_principal_token(
        principal_id=principal_id,
        client_id=tenant_id,
        principal_type="human",
        scopes=scopes or ["completion_projections:repair", "agent_runs:supervise"],
    )
    return {"Authorization": f"Bearer {token}"}


def _governed_incomplete(deps):
    workflow_id = create_workflow(deps)
    outcome_service = _prepare_snapshot(deps, workflow_id, with_result=False)
    _commit(outcome_service, workflow_id)
    return workflow_id, outcome_service


def _read(client, workflow_id, **params):
    return client.get(
        f"/agent-runs/{workflow_id}/completion",
        params={"client_id": TENANT_ID, "user_id": "operator", **params},
    )


def _repair(client, workflow_id, *, key="repair-a", headers=None):
    return client.post(
        f"/agent-runs/{workflow_id}/completion/repair",
        headers=headers or _operator_headers(),
        json={"client_id": TENANT_ID, "idempotency_key": key},
    )


def _restore_repair_trigger() -> None:
    get_connection().executescript(
        (MIGRATIONS_PATH / "052_completion_projection_repair.sql").read_text()
    )


def _insert_raw_repair_receipt(
    *,
    workflow_id: str,
    principal_id: str,
    command_id: str,
    lifecycle_workflow_id: str | None = None,
) -> None:
    conn = get_connection()
    lifecycle = conn.execute(
        """
        SELECT * FROM workflow_completion_lifecycle_events
        WHERE workflow_id = ? ORDER BY authoritative_event_sequence DESC LIMIT 1
        """,
        (lifecycle_workflow_id or workflow_id,),
    ).fetchone()
    projection = conn.execute(
        "SELECT * FROM workflow_completion_projections WHERE workflow_id = ?",
        (workflow_id,),
    ).fetchone()
    outcome = "already_current" if projection is not None else "repaired"
    prior_version = projection["projection_version"] if projection is not None else None
    resulting_version = prior_version if prior_version is not None else 1
    conn.execute(
        """
        INSERT INTO workflow_completion_projection_repairs (
            command_id, tenant_id, workflow_id, principal_type, principal_id,
            authority_source, authority_version, idempotency_key, request_hash,
            outcome, lifecycle_event_id, decision_id, decision_digest,
            authoritative_event_sequence, prior_projection_version,
            resulting_projection_version, completed_at
        ) VALUES (?, ?, ?, 'human', ?, 'agent-principal-token',
                  'agent-principal-signing-secret:v1', ?, ?, ?,
                  ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            command_id,
            TENANT_ID,
            workflow_id,
            principal_id,
            f"idem:{command_id}",
            "a" * 64,
            outcome,
            lifecycle["event_id"],
            lifecycle["decision_id"],
            lifecycle["decision_digest"],
            lifecycle["authoritative_event_sequence"],
            prior_version,
            resulting_version,
            "2026-09-16T10:00:00.000000Z",
        ),
    )


def test_completion_api_exposes_current_authority_and_legacy_runs(completion_api):
    client, deps = completion_api
    legacy_id = create_workflow(deps, tenant_id="tenant-legacy")
    current_id, _ = _governed_incomplete(deps)

    legacy = client.get(
        f"/agent-runs/{legacy_id}/completion",
        params={"client_id": "tenant-legacy", "user_id": "operator"},
    )
    current = _read(client, current_id)

    assert legacy.status_code == 200
    assert legacy.json()["completion"]["authority_state"] == "legacy"
    assert legacy.json()["completion"]["authoritative_decision"] is None
    assert current.status_code == 200
    payload = current.json()["completion"]
    assert payload["authoritative_decision"]["status"] == "incomplete"
    assert payload["authoritative_decision"]["missing_requirements"] == [
        "requirement-a"
    ]
    assert payload["authoritative_decision"]["partial_failures"][
        "missing_result_task_ids"
    ] == ["task-a"]
    assert payload["projection"] == {
        "state": "current",
        "freshness": "current",
        "display_status": "incomplete",
        "authoritative_event_sequence": 0,
        "decision_event_sequence": 0,
        "projected_event_sequence": 0,
        "projection_lag": 0,
        "projection_version": 1,
    }
    assert payload["repair"]["eligible"] is False


def test_missing_projection_repairs_idempotently_from_immutable_event(completion_api):
    client, deps = completion_api
    workflow_id, _ = _governed_incomplete(deps)
    get_connection().execute("DROP TRIGGER workflow_completion_projections_no_delete")
    get_connection().execute(
        "DELETE FROM workflow_completion_projections WHERE workflow_id = ?",
        (workflow_id,),
    )
    get_connection().commit()

    before = _read(client, workflow_id).json()["completion"]
    assert before["projection"]["state"] == "missing"
    assert before["projection"]["display_status"] == "stale"
    assert before["repair"]["eligible"] is True

    repaired = _repair(client, workflow_id)
    replayed = _repair(client, workflow_id)

    assert repaired.status_code == 200
    assert repaired.json()["command"]["outcome"] == "repaired"
    assert repaired.json()["completion"]["projection"]["state"] == "current"
    assert replayed.status_code == 200
    assert replayed.json()["command"]["outcome"] == "replayed"
    assert replayed.json()["command"]["original_outcome"] == "repaired"
    conn = get_connection()
    audit_id = (
        f"completion-projection-repair:{repaired.json()['command']['command_id']}"
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM workflow_completion_projection_repairs"
        ).fetchone()[0]
        == 1
    )
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE event_type = 'completion_projection_repaired'"
        ).fetchone()[0]
        == 1
    )
    with pytest.raises(sqlite3.IntegrityError, match="audit events are immutable"):
        conn.execute(
            "DELETE FROM agent_events WHERE id = ?",
            (audit_id,),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="audit events are immutable"):
        conn.execute(
            """
            UPDATE agent_events SET anchors_json = json('{}')
            WHERE id = ?
            """,
            (audit_id,),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="audit events are immutable"):
        conn.execute(
            """
            INSERT OR REPLACE INTO agent_events (
                id, agent_run_id, sequence, event_type, status, anchors_json
            ) VALUES (?, ?, 0, 'substituted_event', 'tampered', json('{}'))
            """,
            (audit_id, workflow_id),
        )
    conn.rollback()
    protected = conn.execute(
        "SELECT event_type, anchors_json FROM agent_events WHERE id = ?",
        (audit_id,),
    ).fetchone()
    assert protected["event_type"] == "completion_projection_repaired"
    assert protected["anchors_json"] != "{}"
    assert (
        conn.execute(
            "SELECT COUNT(*) FROM agent_events WHERE event_type = 'completion_projection_repaired'"
        ).fetchone()[0]
        == 1
    )


def test_repair_requires_exact_tenant_scoped_operator_authority(completion_api):
    client, deps = completion_api
    workflow_id, _ = _governed_incomplete(deps)
    get_connection().execute("DROP TRIGGER workflow_completion_projections_no_delete")
    get_connection().execute(
        "DELETE FROM workflow_completion_projections WHERE workflow_id = ?",
        (workflow_id,),
    )
    get_connection().commit()

    unauthenticated = client.post(
        f"/agent-runs/{workflow_id}/completion/repair",
        json={"client_id": TENANT_ID, "idempotency_key": "no-auth"},
    )
    wrong_principal = _repair(
        client,
        workflow_id,
        key="wrong-principal",
        headers=_operator_headers(
            principal_id="human:other",
            scopes=["completion_projections:repair"],
        ),
    )
    wrong_tenant = _repair(
        client,
        workflow_id,
        key="wrong-tenant",
        headers=_operator_headers(tenant_id="tenant-b"),
    )

    assert unauthenticated.status_code == 401
    assert wrong_principal.status_code == 403
    assert wrong_tenant.status_code == 403
    with pytest.raises(OutcomeLedgerDataError, match="authority is not trusted"):
        deps.workflow_outcomes.repair_completion_projection(
            command={
                "command_id": "untrusted-source",
                "tenant_id": TENANT_ID,
                "workflow_id": workflow_id,
                "principal_type": "human",
                "principal_id": "human:other",
                "authority_source": "self-asserted",
                "authority_version": "v1",
                "idempotency_key": "untrusted-source",
            }
        )
    direct_bypass = deps.workflow_outcomes.repair_completion_projection(
        command={
            "command_id": "direct-bypass",
            "tenant_id": TENANT_ID,
            "workflow_id": workflow_id,
            "principal_type": "human",
            "principal_id": "human:other",
            "authority_source": "agent-principal-token",
            "authority_version": "agent-principal-signing-secret:v1",
            "idempotency_key": "direct-bypass",
        }
    )
    assert direct_bypass["outcome"] == "conflict"
    assert (
        direct_bypass["reason"] == "repair principal lacks durable operator authority"
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_projection_repairs")
        .fetchone()[0]
        == 0
    )


def test_repair_receipt_trigger_rejects_fabricated_authority_relationship_and_audit(
    completion_api,
):
    _, deps = completion_api
    workflow_id, _ = _governed_incomplete(deps)

    with pytest.raises(sqlite3.IntegrityError, match="operator is invalid"):
        _insert_raw_repair_receipt(
            workflow_id=workflow_id,
            principal_id="human:unregistered",
            command_id="fabricated-unregistered",
        )
    get_connection().rollback()

    ensure_principal(
        principal_id=OPERATOR_ID,
        principal_type="human",
        tenant_id=TENANT_ID,
        metadata={
            "auth_method": "bearer_token",
            "scopes": ["completion_projections:repair", "agent_runs:supervise"],
        },
    )
    other_run = deps.agent_runs.create_agent_run(
        client_id=TENANT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"objective_id": "objective-a"},
        allowed_capabilities=[],
        capability_versions={},
        budgets={},
        approval_policy={},
        requires_approval=False,
        run_mode="observe",
        state="planned",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:planner",
    )
    other_workflow_id = other_run["id"]
    with pytest.raises(sqlite3.IntegrityError, match="lifecycle is invalid"):
        _insert_raw_repair_receipt(
            workflow_id=other_workflow_id,
            lifecycle_workflow_id=workflow_id,
            principal_id=OPERATOR_ID,
            command_id="fabricated-cross-workflow",
        )
    get_connection().rollback()

    with pytest.raises(sqlite3.IntegrityError, match="audit is invalid"):
        _insert_raw_repair_receipt(
            workflow_id=workflow_id,
            principal_id=OPERATOR_ID,
            command_id="fabricated-without-audit",
        )
    get_connection().rollback()
    with pytest.raises(sqlite3.IntegrityError, match="cannot move backward"):
        get_connection().execute(
            """
            UPDATE workflow_completion_projections
            SET projection_version = projection_version + 1
            WHERE tenant_id = ? AND workflow_id = ?
            """,
            (TENANT_ID, workflow_id),
        )
    get_connection().rollback()
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_projection_repairs")
        .fetchone()[0]
        == 0
    )


@pytest.mark.parametrize(
    ("mutation", "expected_state"),
    [
        ("leading", "leading"),
        ("digest", "corrupt"),
    ],
)
def test_projection_semantic_corruption_is_stale_and_repairable(
    completion_api, mutation, expected_state
):
    client, deps = completion_api
    workflow_id, _ = _governed_incomplete(deps)
    conn = get_connection()
    conn.execute("DROP TRIGGER workflow_completion_projection_decision_guard_update")
    if mutation == "leading":
        conn.execute(
            """
            UPDATE workflow_completion_projections
            SET authoritative_event_sequence = authoritative_event_sequence + 1
            WHERE workflow_id = ?
            """,
            (workflow_id,),
        )
    else:
        conn.execute(
            """
            UPDATE workflow_completion_projections
            SET decision_digest = ? WHERE workflow_id = ?
            """,
            ("f" * 64, workflow_id),
        )
    conn.commit()
    _restore_repair_trigger()

    stale = _read(client, workflow_id)
    repaired = _repair(client, workflow_id, key=f"repair-{mutation}")

    assert stale.status_code == 200
    assert stale.json()["completion"]["projection"]["state"] == expected_state
    assert stale.json()["completion"]["projection"]["display_status"] == "stale"
    assert repaired.status_code == 200
    assert repaired.json()["completion"]["projection"]["state"] == "current"


def test_lagging_projection_repairs_to_latest_immutable_decision(completion_api):
    client, deps = completion_api
    workflow_id, outcome_service = _governed_incomplete(deps)
    deps.agent_actions.create_agent_action(
        agent_run_id=workflow_id,
        sequence=2,
        status="proposed",
        capability_name="review_validation_readiness",
        capability_version="v1",
        inputs={},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="Advance immutable completion history",
        confidence=None,
        snapshot_version=None,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
    )
    outcome_service.evaluate_and_commit_lifecycle(
        command=command(
            workflow_id,
            command_id="command-decision-b",
            issued_at=NOW + timedelta(minutes=60),
        ),
        snapshot_id="snapshot-a",
        decision_id="decision-b",
        evaluated_at=NOW + timedelta(minutes=55),
    )
    conn = get_connection()
    first = conn.execute(
        """
        SELECT lifecycle.*, decision.criteria_digest, decision.evaluated_at,
               decision.payload_json
        FROM workflow_completion_lifecycle_events lifecycle
        JOIN workflow_completion_decisions decision
          ON decision.decision_id = lifecycle.decision_id
        WHERE lifecycle.workflow_id = ? AND lifecycle.decision_id = 'decision-a'
        """,
        (workflow_id,),
    ).fetchone()
    conn.execute("DROP TRIGGER workflow_completion_projection_decision_guard_update")
    conn.execute(
        """
        UPDATE workflow_completion_projections
        SET decision_id = ?, decision_digest = ?, criteria_digest = ?,
            completion_status = ?, projected_run_status = ?, projected_run_state = ?,
            authoritative_event_sequence = ?, action_projection_digest = ?,
            blockers_json = json_extract(?, '$.blockers'), evaluated_at = ?
        WHERE workflow_id = ?
        """,
        (
            first["decision_id"],
            first["decision_digest"],
            first["criteria_digest"],
            first["completion_status"],
            first["projected_run_status"],
            first["projected_run_state"],
            first["authoritative_event_sequence"],
            first["action_projection_digest"],
            first["payload_json"],
            first["evaluated_at"],
            workflow_id,
        ),
    )
    conn.commit()
    _restore_repair_trigger()

    lagging = _read(client, workflow_id).json()["completion"]
    repaired = _repair(client, workflow_id, key="repair-lagging")

    assert lagging["projection"]["state"] == "lagging"
    assert lagging["projection"]["projection_lag"] == 1
    assert repaired.status_code == 200
    assert (
        repaired.json()["completion"]["authoritative_decision"]["decision_id"]
        == "decision-b"
    )
    assert repaired.json()["completion"]["projection"]["state"] == "current"


def test_state_drift_blocks_stale_projection_repair(completion_api):
    client, deps = completion_api
    workflow_id, _ = _governed_incomplete(deps)
    get_connection().execute(
        "UPDATE agent_runs SET state = 'concurrent-drift' WHERE id = ?",
        (workflow_id,),
    )
    get_connection().commit()

    stale = _read(client, workflow_id).json()["completion"]
    repair = _repair(client, workflow_id, key="repair-drift")

    assert stale["projection"]["state"] == "stale"
    assert stale["repair"] == {
        "eligible": False,
        "reason": "authoritative_state_changed",
        "last_outcome": None,
    }
    assert repair.status_code == 409
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM workflow_completion_projection_repairs")
        .fetchone()[0]
        == 0
    )


def test_corrupt_authoritative_lifecycle_fails_closed(completion_api):
    client, deps = completion_api
    workflow_id, _ = _governed_incomplete(deps)
    get_connection().execute(
        "DROP TRIGGER workflow_completion_lifecycle_events_no_update"
    )
    get_connection().execute(
        """
        UPDATE workflow_completion_lifecycle_events
        SET decision_digest = ? WHERE workflow_id = ?
        """,
        ("f" * 64, workflow_id),
    )
    get_connection().commit()

    response = _read(client, workflow_id)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "completion_projection_integrity_error"
