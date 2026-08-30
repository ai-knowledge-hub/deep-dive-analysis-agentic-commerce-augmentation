from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier
import json
import sqlite3

import pytest

from api.composition import default_deps
from application.services.agent_runtime.approval_ledger import (
    ApprovalLedgerError,
    issue_action_approval_command,
    list_action_approvals,
)
from domain.workflow.approval import ApprovalAuthority, PrincipalType
from shared.db.connection import get_connection, init_db, set_database_path


TENANT_ID = "client-a"


@pytest.fixture
def ledger(tmp_path):
    db_path = tmp_path / "approval-ledger.db"
    set_database_path(db_path)
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id=TENANT_ID, name="Client A")
    return deps, db_path


def _authority(principal_id: str = "human:user-a") -> ApprovalAuthority:
    return ApprovalAuthority(
        principal_type=PrincipalType.HUMAN,
        principal_id=principal_id,
        authority_source="test-user-context",
        authority_version="v1",
    )


def _run_and_action(
    deps,
    *,
    sequence: int = 1,
    inputs: dict | None = None,
    status: str = "proposed",
):
    run = deps.agent_runs.create_agent_run(
        client_id=TENANT_ID,
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"goal": "governed test effect"},
        allowed_capabilities=["run_variant"],
        capability_versions={"run_variant": "v1"},
        budgets={"actions": 1},
        approval_policy={"approval_ttl_seconds": 900},
        requires_approval=True,
        run_mode="plan_only",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:test",
        harness_id="operator_supervised",
        policy_profile_id="human_approval_required",
        registry_version="registry-v1",
        registry_fingerprint="a" * 64,
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=sequence,
        status=status,
        capability_name="run_variant",
        capability_version="v1",
        inputs=inputs or {"experiment_id": "experiment-a"},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="test governed action",
        confidence=0.8,
        snapshot_version=1,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
        registry_version="registry-v1",
        registry_fingerprint="a" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class="write_low_risk",
        dedupe_key=f"effect-{sequence}",
    )
    return run, action


def _additional_action(
    deps,
    run: dict,
    *,
    sequence: int,
    inputs: dict | None = None,
    status: str = "proposed",
) -> dict:
    return deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=sequence,
        status=status,
        capability_name="run_variant",
        capability_version="v1",
        inputs=inputs or {"experiment_id": f"experiment-{sequence}"},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="additional governed action",
        confidence=0.8,
        snapshot_version=sequence,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
        registry_version="registry-v1",
        registry_fingerprint="a" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class="write_low_risk",
        dedupe_key=f"effect-{sequence}",
    )


def test_decision_persists_exact_snapshots_events_and_authority_across_restart(
    ledger,
):
    deps, db_path = ledger
    run, action = _run_and_action(deps)

    response = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=_authority(),
        idempotency_key="approve-action-1",
        occurred_at=datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc),
    )

    approval = response["approval"]
    assert approval["status"] == "approved"
    assert approval["sequence"] == 2
    assert response["action"]["status"] == "approved"
    assert response["command"]["principal_id"] == "human:user-a"
    assert response["command"]["request_hash"] != approval["envelope_digest"]

    events = deps.approval_ledger.list_approval_events(
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        approval_id=approval["approval_id"],
    )
    assert [event["event_type"] for event in events] == [
        "approval_requested",
        "approval_approved",
    ]
    assert {event["principal_id"] for event in events} == {"human:user-a"}
    assert events[-1]["envelope_digest"] == approval["envelope_digest"]

    audit = deps.agent_events.list_agent_events(agent_run_id=run["id"])
    assert {item["event_type"] for item in audit} >= {
        "approval_approved",
        "action_approved",
    }
    assert all("inputs" not in item["anchors"] for item in audit)

    set_database_path(db_path)
    init_db()
    restarted = default_deps()
    persisted = list_action_approvals(
        deps=restarted,
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        action_id=action["id"],
    )
    assert len(persisted) == 1
    assert persisted[0]["envelope_digest"] == approval["envelope_digest"]
    assert len(persisted[0]["events"]) == 2


def test_identical_command_replays_without_duplicate_history_and_key_reuse_fails(
    ledger,
):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    kwargs = {
        "deps": deps,
        "run": run,
        "action": action,
        "command_type": "approve",
        "approving_authority": _authority(),
        "idempotency_key": "same-key",
        "occurred_at": datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc),
    }

    first = issue_action_approval_command(**kwargs)
    replay = issue_action_approval_command(**kwargs)

    assert replay["replayed"] is True
    assert replay["command"]["command_id"] == first["command"]["command_id"]
    events = deps.approval_ledger.list_approval_events(
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        approval_id=first["approval"]["approval_id"],
    )
    assert len(events) == 2

    with pytest.raises(ApprovalLedgerError, match="different approval command") as exc:
        issue_action_approval_command(
            **{**kwargs, "command_type": "reject"},
        )
    assert exc.value.code == "idempotency_key_reused"


@pytest.mark.parametrize(
    ("action_status", "command_type"),
    [
        ("executing", "approve"),
        ("executed", "approve"),
        ("failed", "approve"),
        ("rejected", "approve"),
        ("executed", "request"),
        ("failed", "reject"),
    ],
)
def test_new_commands_cannot_resurrect_non_decidable_actions(
    ledger,
    action_status: str,
    command_type: str,
):
    deps, _ = ledger
    run, action = _run_and_action(deps, status=action_status)

    with pytest.raises(ApprovalLedgerError, match="current lifecycle state") as exc:
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=action,
            command_type=command_type,
            approving_authority=_authority(),
            idempotency_key=f"{command_type}-{action_status}",
        )

    assert exc.value.code == "action_not_decidable"
    assert deps.agent_actions.get_agent_action(action["id"])["status"] == action_status
    assert (
        deps.approval_ledger.list_approvals_for_action(
            tenant_id=TENANT_ID,
            workflow_id=run["id"],
            action_id=action["id"],
        )
        == []
    )


def test_identical_replay_cannot_rewrite_a_later_terminal_action(ledger):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    kwargs = {
        "deps": deps,
        "run": run,
        "action": action,
        "command_type": "approve",
        "approving_authority": _authority(),
        "idempotency_key": "approve-before-execution",
    }
    committed = issue_action_approval_command(**kwargs)
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"],
        status="executed",
        outputs={"receipt": "already-committed"},
    )

    replay = issue_action_approval_command(**kwargs)

    assert replay["replayed"] is True
    assert replay["command"]["command_id"] == committed["command"]["command_id"]
    assert replay["action"]["status"] == "executed"
    assert (
        len(
            deps.approval_ledger.list_approval_events(
                tenant_id=TENANT_ID,
                workflow_id=run["id"],
                approval_id=committed["approval"]["approval_id"],
            )
        )
        == 2
    )


def test_action_status_is_compared_again_inside_approval_commit(ledger, monkeypatch):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    original_commit = deps.approval_ledger.commit_approval_command

    def terminalize_before_commit(**kwargs):
        deps.agent_actions.update_agent_action_status(
            action_id=action["id"], status="executed", outputs={}
        )
        return original_commit(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_approval_command", terminalize_before_commit
    )

    with pytest.raises(ApprovalLedgerError, match="lifecycle state changed") as exc:
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=action,
            command_type="approve",
            approving_authority=_authority(),
            idempotency_key="status-race",
        )

    assert exc.value.code == "action_state_conflict"
    assert deps.agent_actions.get_agent_action(action["id"])["status"] == "executed"
    assert (
        deps.approval_ledger.list_approvals_for_action(
            tenant_id=TENANT_ID,
            workflow_id=run["id"],
            action_id=action["id"],
        )
        == []
    )


def test_adapter_rejects_self_selected_terminal_source_status(ledger, monkeypatch):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    original_commit = deps.approval_ledger.commit_approval_command

    def forge_expected_terminal_status(**kwargs):
        deps.agent_actions.update_agent_action_status(
            action_id=action["id"], status="executed", outputs={}
        )
        return original_commit(**{**kwargs, "expected_action_status": "executed"})

    monkeypatch.setattr(
        deps.approval_ledger,
        "commit_approval_command",
        forge_expected_terminal_status,
    )

    with pytest.raises(ApprovalLedgerError, match="lifecycle state changed") as exc:
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=action,
            command_type="approve",
            approving_authority=_authority(),
            idempotency_key="forged-terminal-expectation",
        )

    assert exc.value.code == "action_state_conflict"
    assert deps.agent_actions.get_agent_action(action["id"])["status"] == "executed"
    assert (
        deps.approval_ledger.list_approvals_for_action(
            tenant_id=TENANT_ID,
            workflow_id=run["id"],
            action_id=action["id"],
        )
        == []
    )


def test_concurrent_conflicting_decisions_have_one_winner(ledger, monkeypatch):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    original_commit = deps.approval_ledger.commit_approval_command
    barrier = Barrier(2)

    def synchronized_commit(**kwargs):
        barrier.wait(timeout=5)
        return original_commit(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_approval_command", synchronized_commit
    )

    def decide(command_type: str):
        try:
            result = issue_action_approval_command(
                deps=deps,
                run=run,
                action=action,
                command_type=command_type,
                approving_authority=_authority(f"human:{command_type}"),
                idempotency_key=f"decision-{command_type}",
                occurred_at=datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc),
            )
            return result["approval"]["status"]
        except ApprovalLedgerError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = set(executor.map(decide, ["approve", "reject"]))

    assert outcomes & {"approval_version_conflict", "action_state_conflict"}
    assert len(outcomes & {"approved", "rejected"}) == 1
    records = deps.approval_ledger.list_approvals_for_action(
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        action_id=action["id"],
    )
    assert len(records) == 1


def test_amended_action_cannot_inherit_prior_approval(ledger):
    deps, _ = ledger
    run, original = _run_and_action(deps, inputs={"budget": 10})
    approved = issue_action_approval_command(
        deps=deps,
        run=run,
        action=original,
        command_type="approve",
        approving_authority=_authority(),
        idempotency_key="approve-original",
    )
    amended = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="proposed",
        capability_name="run_variant",
        capability_version="v1",
        inputs={"budget": 11},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="amended governed action",
        confidence=0.8,
        snapshot_version=2,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
        registry_version="registry-v1",
        registry_fingerprint="a" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class="write_low_risk",
        dedupe_key="effect-2",
    )

    requested = issue_action_approval_command(
        deps=deps,
        run=run,
        action=amended,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-amendment",
    )

    assert requested["approval"]["status"] == "requested"
    assert requested["approval"]["approval_id"] != approved["approval"]["approval_id"]
    assert (
        requested["approval"]["envelope_digest"]
        != approved["approval"]["envelope_digest"]
    )
    assert requested["approval"]["envelope"]["scope"]["action_id"] == amended["id"]


def test_expiry_and_supersession_fail_closed_on_time_scope_and_cycles(ledger):
    deps, _ = ledger
    run, source_action = _run_and_action(deps)
    requested_at = datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc)
    source = issue_action_approval_command(
        deps=deps,
        run=run,
        action=source_action,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-source",
        occurred_at=requested_at,
        ttl_seconds=60,
    )
    with pytest.raises(ApprovalLedgerError, match="cannot expire before"):
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=source_action,
            command_type="expire",
            approval_id=source["approval"]["approval_id"],
            approving_authority=_authority(),
            idempotency_key="expire-too-early",
            occurred_at=requested_at + timedelta(seconds=59),
        )

    replacement_action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=2,
        status="proposed",
        capability_name="run_variant",
        capability_version="v1",
        inputs={"experiment_id": "experiment-b"},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="replacement",
        confidence=0.8,
        snapshot_version=2,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
        registry_version="registry-v1",
        registry_fingerprint="a" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class="write_low_risk",
        dedupe_key="effect-2",
    )
    replacement = issue_action_approval_command(
        deps=deps,
        run=run,
        action=replacement_action,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-replacement",
        occurred_at=requested_at + timedelta(seconds=1),
    )
    superseded = issue_action_approval_command(
        deps=deps,
        run=run,
        action=source_action,
        command_type="supersede",
        approval_id=source["approval"]["approval_id"],
        supersession_reference=replacement["approval"]["approval_id"],
        approving_authority=_authority(),
        idempotency_key="supersede-source",
        occurred_at=requested_at + timedelta(seconds=2),
    )
    assert superseded["approval"]["status"] == "superseded"

    with pytest.raises(ApprovalLedgerError, match="cycle"):
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=replacement_action,
            command_type="supersede",
            approval_id=replacement["approval"]["approval_id"],
            supersession_reference=source["approval"]["approval_id"],
            approving_authority=_authority(),
            idempotency_key="supersede-cycle",
            occurred_at=requested_at + timedelta(seconds=3),
        )


def test_concurrent_reciprocal_supersessions_cannot_commit_a_cycle(ledger, monkeypatch):
    deps, _ = ledger
    run, action_a = _run_and_action(deps)
    action_b = _additional_action(deps, run, sequence=2)
    requested_at = datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc)
    approval_a = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action_a,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-cycle-a",
        occurred_at=requested_at,
    )["approval"]
    approval_b = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action_b,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-cycle-b",
        occurred_at=requested_at,
    )["approval"]
    original_commit = deps.approval_ledger.commit_approval_command
    barrier = Barrier(2)

    def synchronized_commit(**kwargs):
        barrier.wait(timeout=5)
        return original_commit(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_approval_command", synchronized_commit
    )

    def supersede(source_action: dict, source: dict, replacement: dict, suffix: str):
        try:
            result = issue_action_approval_command(
                deps=deps,
                run=run,
                action=source_action,
                command_type="supersede",
                approval_id=source["approval_id"],
                supersession_reference=replacement["approval_id"],
                approving_authority=_authority(f"human:{suffix}"),
                idempotency_key=f"supersede-cycle-{suffix}",
                occurred_at=requested_at + timedelta(seconds=1),
            )
            return result["approval"]["status"]
        except ApprovalLedgerError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(supersede, action_a, approval_a, approval_b, "a-to-b"),
            executor.submit(supersede, action_b, approval_b, approval_a, "b-to-a"),
        ]
        outcomes = {future.result(timeout=10) for future in futures}

    assert outcomes == {"superseded", "supersession_cycle"}
    records = {
        row["approval_id"]: row
        for action in (action_a, action_b)
        for row in deps.approval_ledger.list_approvals_for_action(
            tenant_id=TENANT_ID,
            workflow_id=run["id"],
            action_id=action["id"],
        )
    }
    links = {
        approval_id: str(
            dict(row["envelope"].get("lifecycle") or {}).get("supersession_reference")
            or ""
        )
        for approval_id, row in records.items()
        if row["status"] == "superseded"
    }
    assert len(links) == 1
    assert not all(links.get(target) == source for source, target in links.items())


def test_supersession_rejects_projection_rollback_against_immutable_history(ledger):
    deps, _ = ledger
    run, action_a = _run_and_action(deps)
    action_b = _additional_action(deps, run, sequence=2)
    requested_at = datetime(2026, 8, 28, 9, 0, tzinfo=timezone.utc)
    approval_a = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action_a,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-rollback-a",
        occurred_at=requested_at,
    )["approval"]
    approval_b = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action_b,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-rollback-b",
        occurred_at=requested_at,
    )["approval"]
    issue_action_approval_command(
        deps=deps,
        run=run,
        action=action_a,
        command_type="supersede",
        approval_id=approval_a["approval_id"],
        supersession_reference=approval_b["approval_id"],
        approving_authority=_authority(),
        idempotency_key="supersede-rollback-a",
        occurred_at=requested_at + timedelta(seconds=1),
    )
    immutable_events = deps.approval_ledger.list_approval_events(
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        approval_id=approval_a["approval_id"],
    )
    requested_event = immutable_events[0]
    get_connection().execute(
        """
        UPDATE approval_records
        SET current_sequence = ?, current_status = ?, envelope_json = json(?),
            envelope_digest = ?
        WHERE approval_id = ?
        """,
        (
            requested_event["sequence"],
            requested_event["status"],
            json.dumps(requested_event["envelope"]),
            requested_event["envelope_digest"],
            approval_a["approval_id"],
        ),
    )
    get_connection().commit()

    with pytest.raises(ApprovalLedgerError, match="append-only history") as exc:
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=action_b,
            command_type="supersede",
            approval_id=approval_b["approval_id"],
            supersession_reference=approval_a["approval_id"],
            approving_authority=_authority(),
            idempotency_key="supersede-rollback-b",
            occurred_at=requested_at + timedelta(seconds=2),
        )

    assert exc.value.code == "corrupt_approval_history"
    events_b = deps.approval_ledger.list_approval_events(
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        approval_id=approval_b["approval_id"],
    )
    assert [event["status"] for event in events_b] == ["requested"]


def test_tenant_scope_and_tamper_checks_use_independent_ledger_authority(ledger):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    approved = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=_authority(),
        idempotency_key="approve-for-tamper-test",
    )
    approval_id = approved["approval"]["approval_id"]
    assert (
        deps.approval_ledger.get_approval(
            approval_id=approval_id,
            tenant_id="client-b",
            workflow_id=run["id"],
        )
        is None
    )

    get_connection().execute(
        "UPDATE approval_records SET envelope_digest = ? WHERE approval_id = ?",
        ("0" * 64, approval_id),
    )
    get_connection().commit()
    with pytest.raises(ApprovalLedgerError, match="digest does not match"):
        list_action_approvals(
            deps=deps,
            tenant_id=TENANT_ID,
            workflow_id=run["id"],
            action_id=action["id"],
        )


def test_migration_makes_history_and_command_receipts_immutable(ledger):
    deps, _ = ledger
    run, action = _run_and_action(deps)
    response = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=_authority(),
        idempotency_key="immutable-receipt",
    )
    approval_id = response["approval"]["approval_id"]
    command_id = response["command"]["command_id"]
    event_id = deps.approval_ledger.list_approval_events(
        tenant_id=TENANT_ID,
        workflow_id=run["id"],
        approval_id=approval_id,
    )[0]["event_id"]

    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        get_connection().execute(
            "UPDATE approval_events SET status = 'rejected' WHERE event_id = ?",
            (event_id,),
        )
    get_connection().rollback()
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        get_connection().execute(
            "DELETE FROM approval_commands WHERE command_id = ?", (command_id,)
        )
    get_connection().rollback()
    with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
        get_connection().execute(
            "DELETE FROM approval_records WHERE approval_id = ?", (approval_id,)
        )
    get_connection().rollback()
