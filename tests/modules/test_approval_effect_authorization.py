from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import sqlite3

import pytest

from api.composition import default_deps
from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    commit_pre_effect_authorization,
    mark_authorized_effect_uncertain,
    reconcile_authorized_effect,
    validate_exact_action_approval,
)
from application.services.agent_runtime.approval_ledger import (
    ApprovalLedgerError,
    issue_action_approval_command,
)
from application.services.agent_runtime.registry import get_capability_spec
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from domain.workflow.approval import ApprovalAuthority, PrincipalType
from shared.db.connection import get_connection, init_db, set_database_path


def _authority() -> ApprovalAuthority:
    return ApprovalAuthority(
        principal_type=PrincipalType.HUMAN,
        principal_id="human:operator-a",
        authority_source="verified-test-claims",
        authority_version="v1",
    )


def _run_and_action(
    tmp_path,
    *,
    capability_name: str = "request_synthetic_validation",
    dedupe_key: str = "effect:validation:1",
    status: str = "proposed",
):
    set_database_path(tmp_path / "approval-effect.db")
    init_db()
    deps = default_deps()
    deps.clients.create_client(client_id="client-a", name="Client A")
    spec = get_capability_spec(capability_name)
    assert spec is not None
    registry_fingerprint = "a" * 64
    run = deps.agent_runs.create_agent_run(
        client_id="client-a",
        brand_id=None,
        product_id=None,
        experiment_id=None,
        objective={"goal": "governed effect"},
        allowed_capabilities=[capability_name],
        capability_versions={capability_name: "v1"},
        budgets={"max_actions": 2},
        approval_policy={"approval_ttl_seconds": 900},
        requires_approval=True,
        run_mode="auto_execute_safe",
        state="battery_ready",
        status="planned",
        principal_type="internal_agent",
        principal_id="internal-agent:planner-a",
        harness_id=None,
        policy_profile_id="human_approval_required",
        registry_version="registry-v1",
        registry_fingerprint=registry_fingerprint,
    )
    action = deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=1,
        status=status,
        capability_name=capability_name,
        capability_version="v1",
        inputs={"experiment_id": "experiment-a"},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale="request exact governed effect",
        confidence=0.8,
        snapshot_version=1,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id=spec.tool_id,
        skill_id="optimize-product-representation",
        registry_version="registry-v1",
        registry_fingerprint=registry_fingerprint,
        tool_version="v1",
        skill_version="v1",
        effect_class=spec.effect_class,
        dedupe_key=dedupe_key,
    )
    return deps, run, action, spec


def _approve(deps, run, action, *, occurred_at: datetime | None = None):
    return issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=_authority(),
        idempotency_key=f"approve:{action['id']}",
        occurred_at=occurred_at,
    )


def _additional_action(
    deps,
    run,
    spec,
    *,
    sequence: int = 2,
    dedupe_key: str = "effect:validation:2",
):
    return deps.agent_actions.create_agent_action(
        agent_run_id=run["id"],
        sequence=sequence,
        status="proposed",
        capability_name=spec.name,
        capability_version="v1",
        inputs={"experiment_id": f"experiment-{sequence}"},
        outputs={},
        inputs_hash=None,
        outputs_hash=None,
        rationale=f"replacement action {sequence}",
        confidence=0.7,
        snapshot_version=sequence,
        hypothesis_id=None,
        variant_id=None,
        validation_job_id=None,
        tool_id=spec.tool_id,
        skill_id="optimize-product-representation",
        registry_version="registry-v1",
        registry_fingerprint="a" * 64,
        tool_version="v1",
        skill_version="v1",
        effect_class=spec.effect_class,
        dedupe_key=dedupe_key,
    )


def test_governed_effect_cannot_execute_from_action_status_alone(tmp_path, monkeypatch):
    deps, run, action, _ = _run_and_action(tmp_path, status="approved")
    called = False

    def _unexpected_effect(**kwargs):
        nonlocal called
        called = True
        return {"validation_job_id": "job-1"}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        _unexpected_effect,
    )

    with pytest.raises(AgentRuntimeError, match="canonical approval_id"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    assert called is False
    denied = next(
        event
        for event in deps.agent_events.list_agent_events(agent_run_id=run["id"])
        if event["event_type"] == "approval_authorization_denied"
    )
    assert denied["anchors"]["denial_code"] == "missing_approval_id"
    assert denied["anchors"]["authorization_phase"] == "admission"
    assert denied["action_id"] == action["id"]


def test_exact_approval_is_consumed_fulfilled_and_linked_to_receipt(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    assert approved["action"]["approval_id"] == approved["approval"]["approval_id"]
    assert (
        approved["action"]["approval_envelope_digest"]
        == approved["approval"]["envelope_digest"]
    )

    calls = 0

    def _effect(**kwargs):
        nonlocal calls
        calls += 1
        return {"validation_job_id": "job-1"}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )

    assert calls == 1
    assert result.action is not None
    assert result.action["status"] == "executed"
    assert result.action["receipt_id"].startswith("approval-effect-receipt:")
    effect = deps.approval_ledger.get_effect_execution(
        tenant_id="client-a",
        workflow_id=run["id"],
        effect_idempotency_key="effect:validation:1",
    )
    assert effect["status"] == "succeeded"
    assert effect["receipt_id"] == result.action["receipt_id"]
    approval = deps.approval_ledger.get_approval(
        tenant_id="client-a",
        workflow_id=run["id"],
        approval_id=approved["approval"]["approval_id"],
    )
    assert approval["status"] == "fulfilled"
    assert (
        approval["envelope"]["lifecycle"]["fulfillment_receipt_id"]
        == effect["receipt_id"]
    )
    event_types = {
        event["event_type"]
        for event in deps.agent_events.list_agent_events(agent_run_id=run["id"])
    }
    assert {
        "approval_effect_started",
        "approval_effect_succeeded",
        "approval_fulfilled",
        "action_executed",
    } <= event_types


@pytest.mark.parametrize(
    ("statement", "params", "expected_field"),
    [
        (
            "UPDATE agent_runs SET principal_id = ?",
            ("internal-agent:other",),
            "principal_id",
        ),
        (
            "UPDATE agent_runs SET active_graph_revision = ?",
            (2,),
            "active_graph_revision",
        ),
        ("UPDATE agent_runs SET harness_id = ?", ("different-harness",), "harness_id"),
        (
            "UPDATE agent_runs SET policy_profile_id = ?",
            ("observe",),
            "policy_profile_id",
        ),
        (
            "UPDATE agent_runs SET budgets_json = json(?)",
            (json.dumps({"max_actions": 3}),),
            "authority_hash",
        ),
        (
            "UPDATE agent_actions SET inputs_json = json(?), inputs_hash = NULL",
            (json.dumps({"experiment_id": "experiment-b"}),),
            "input_hash",
        ),
        (
            "UPDATE agent_actions SET inputs_hash = ?",
            ("f" * 64,),
            "binding_source",
        ),
        (
            "UPDATE agent_actions SET rationale_text = ?",
            ("different evidence",),
            "evidence_digest",
        ),
        (
            "UPDATE agent_actions SET capability_name = ?",
            ("seed_hypotheses",),
            "capability_id",
        ),
        ("UPDATE agent_actions SET capability_version = ?", ("v2",), "payload_hash"),
        (
            "UPDATE agent_actions SET tool_id = ?",
            ("experiment.run_variant",),
            "tool_id",
        ),
        ("UPDATE agent_actions SET tool_version = ?", ("v2",), "payload_hash"),
        (
            "UPDATE agent_actions SET effect_class = ?",
            ("write_low_risk",),
            "effect_class",
        ),
        (
            "UPDATE agent_actions SET registry_fingerprint = ?",
            ("b" * 64,),
            "registry_fingerprint",
        ),
    ],
)
def test_every_mutable_binding_dimension_fails_closed(
    tmp_path, statement, params, expected_field
):
    deps, run, action, spec = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    conn = get_connection()
    target_id = run["id"] if "agent_runs" in statement else action["id"]
    conn.execute(f"{statement} WHERE id = ?", (*params, target_id))
    conn.commit()
    current_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    current_action = deps.agent_actions.get_agent_action(action_id=action["id"])

    with pytest.raises(ApprovalAuthorizationError) as exc:
        validate_exact_action_approval(
            deps=deps,
            run=current_run,
            action=current_action,
            spec=spec,
        )

    assert expected_field in exc.value.mismatches
    assert approved["approval"]["status"] == "approved"


def test_expiry_is_checked_again_at_execution_time(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    decided_at = datetime.now(timezone.utc) - timedelta(seconds=10)
    approved = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=_authority(),
        idempotency_key="expired-before-execution",
        occurred_at=decided_at,
        ttl_seconds=1,
    )

    with pytest.raises(ApprovalAuthorizationError) as exc:
        validate_exact_action_approval(
            deps=deps,
            run=run,
            action=approved["action"],
            spec=spec,
            now=datetime.now(timezone.utc),
        )

    assert exc.value.code == "approval_expired"


def test_approval_cannot_cross_tenant_or_action_scope(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    other_action = _additional_action(deps, run, spec)
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_actions
        SET status = 'executing', approval_id = ?, approval_envelope_digest = ?
        WHERE id = ?
        """,
        (
            approved["approval"]["approval_id"],
            approved["approval"]["envelope_digest"],
            other_action["id"],
        ),
    )
    conn.commit()

    with pytest.raises(ApprovalAuthorizationError) as action_exc:
        validate_exact_action_approval(
            deps=deps,
            run=run,
            action=deps.agent_actions.get_agent_action(action_id=other_action["id"]),
            spec=spec,
        )
    assert action_exc.value.code == "approval_action_mismatch"

    deps.clients.create_client(client_id="client-b", name="Client B")
    conn.execute(
        "UPDATE agent_runs SET client_id = 'client-b' WHERE id = ?", (run["id"],)
    )
    conn.commit()
    changed_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    changed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    with pytest.raises(ApprovalAuthorizationError) as tenant_exc:
        validate_exact_action_approval(
            deps=deps,
            run=changed_run,
            action=changed_action,
            spec=spec,
        )
    assert tenant_exc.value.code == "approval_not_found"


def test_superseded_approval_stays_terminal_at_execution_boundary(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    source = _approve(deps, run, action)
    replacement_action = _additional_action(deps, run, spec)
    replacement = issue_action_approval_command(
        deps=deps,
        run=run,
        action=replacement_action,
        command_type="request",
        approving_authority=_authority(),
        idempotency_key="request-replacement",
    )
    superseded = issue_action_approval_command(
        deps=deps,
        run=run,
        action=source["action"],
        command_type="supersede",
        approval_id=source["approval"]["approval_id"],
        supersession_reference=replacement["approval"]["approval_id"],
        approving_authority=_authority(),
        idempotency_key="supersede-before-effect",
    )
    conn = get_connection()
    conn.execute(
        "UPDATE agent_actions SET status = 'executing' WHERE id = ?", (action["id"],)
    )
    conn.commit()

    with pytest.raises(ApprovalAuthorizationError) as exc:
        validate_exact_action_approval(
            deps=deps,
            run=run,
            action=deps.agent_actions.get_agent_action(action_id=action["id"]),
            spec=spec,
        )

    assert superseded["approval"]["status"] == "superseded"
    assert exc.value.code == "approval_not_active"


def test_revocation_wins_when_it_commits_before_pre_effect_authorization(
    tmp_path, monkeypatch
):
    deps, run, action, spec = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    original = deps.approval_ledger.commit_effect_authorization

    def _revoke_first(**kwargs):
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=executing,
            command_type="revoke",
            approval_id=approved["approval"]["approval_id"],
            approving_authority=_authority(),
            idempotency_key="race-revocation-wins",
            revocation_reference="operator-stop",
        )
        return original(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_effect_authorization", _revoke_first
    )

    with pytest.raises(ApprovalAuthorizationError) as exc:
        commit_pre_effect_authorization(deps=deps, run=run, action=executing, spec=spec)

    assert exc.value.code == "approval_changed_before_effect"
    assert (
        deps.approval_ledger.get_effect_execution(
            tenant_id="client-a",
            workflow_id=run["id"],
            effect_idempotency_key="effect:validation:1",
        )
        is None
    )


def test_pre_effect_commit_wins_race_and_prevents_late_revocation(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = commit_pre_effect_authorization(
        deps=deps, run=run, action=executing, spec=spec
    )
    assert authorization is not None

    with pytest.raises(ApprovalLedgerError) as exc:
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=executing,
            command_type="revoke",
            approval_id=approved["approval"]["approval_id"],
            approving_authority=_authority(),
            idempotency_key="race-effect-wins",
            revocation_reference="too-late",
        )

    assert exc.value.code == "effect_already_started"


def test_effect_identity_and_outcome_state_cannot_be_rewritten(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = commit_pre_effect_authorization(
        deps=deps, run=run, action=executing, spec=spec
    )
    assert authorization is not None
    conn = get_connection()

    with pytest.raises(sqlite3.IntegrityError, match="identity is immutable"):
        conn.execute(
            """
            UPDATE approval_effect_executions
            SET effect_idempotency_key = 'different-effect',
                status = 'uncertain', error_code = 'tampered'
            WHERE execution_id = ?
            """,
            (authorization.execution_id,),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """
            UPDATE approval_effect_executions
            SET status = 'succeeded'
            WHERE execution_id = ?
            """,
            (authorization.execution_id,),
        )
    conn.rollback()

    effect = deps.approval_ledger.get_effect_execution(
        tenant_id="client-a",
        workflow_id=run["id"],
        effect_idempotency_key="effect:validation:1",
    )
    assert effect["status"] == "started"


def test_uncertain_same_effect_reconciles_after_restart_without_second_execution(
    tmp_path,
):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = commit_pre_effect_authorization(
        deps=deps, run=run, action=executing, spec=spec
    )
    assert authorization is not None
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=executing,
        authorization=authorization,
        error_code="provider_timeout",
    )
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"],
        status="failed",
        outputs={},
        outputs_hash=hash_payload({}),
        error="provider timeout after effect start",
    )

    outputs = {"validation_job_id": "job-reconciled"}
    reloaded_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    reloaded_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    reconciled = reconcile_authorized_effect(
        deps=deps,
        run=reloaded_run,
        action=reloaded_action,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id="provider-receipt:job-reconciled",
    )

    assert reconciled["status"] == "succeeded"
    persisted = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert persisted["status"] == "executed"
    assert persisted["receipt_id"] == "provider-receipt:job-reconciled"

    duplicate = reconcile_authorized_effect(
        deps=deps,
        run=deps.agent_runs.get_agent_run(run_id=run["id"]),
        action=persisted,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id="provider-receipt:job-reconciled",
    )
    assert duplicate == reconciled

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=deps.agent_runs.get_agent_run(run_id=run["id"]),
            action=persisted,
            spec=spec,
            outputs={"validation_job_id": "different"},
            outputs_hash=hash_payload({"validation_job_id": "different"}),
            receipt_id="provider-receipt:different",
        )
    assert exc.value.code == "effect_identity_conflict"


def test_same_effect_identity_cannot_be_reused_by_a_second_action(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    first = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    commit_pre_effect_authorization(deps=deps, run=run, action=first, spec=spec)

    second = _additional_action(deps, run, spec, dedupe_key="effect:validation:1")
    approved_second = _approve(deps, run, second)
    second_executing = deps.agent_actions.transition_agent_action_status(
        action_id=second["id"], from_status="approved", to_status="executing"
    )

    with pytest.raises(ApprovalAuthorizationError) as exc:
        commit_pre_effect_authorization(
            deps=deps,
            run=run,
            action=second_executing,
            spec=spec,
        )

    assert exc.value.code == "effect_identity_conflict"
    assert approved_second["approval"]["status"] == "approved"
