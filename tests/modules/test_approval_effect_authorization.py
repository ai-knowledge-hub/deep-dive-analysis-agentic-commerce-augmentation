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
from application.services.agent_runtime.registry import (
    REGISTRY_VERSION,
    registry_contract_payload,
)
from application.services.agent_runtime.registry.hashing import hash_registry_payload
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from shared.db.connection import get_connection, init_db, set_database_path
from tests.modules.approval_effect_support import (
    approval_authority,
    matching_validation_job as _matching_validation_job,
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
    registry_payload = registry_contract_payload()
    registry_fingerprint = hash_registry_payload(registry_payload)
    deps.agent_registry.ensure_agent_registry_version(
        registry_version=REGISTRY_VERSION,
        registry_fingerprint=registry_fingerprint,
        payload=registry_payload,
    )
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
        registry_version=REGISTRY_VERSION,
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
        registry_version=REGISTRY_VERSION,
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
        approving_authority=approval_authority(),
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
        registry_version=run["registry_version"],
        registry_fingerprint=run["registry_fingerprint"],
        tool_version="v1",
        skill_version="v1",
        effect_class=spec.effect_class,
        dedupe_key=dedupe_key,
    )


def _execution_lease(deps, run, *, token: str = "worker-a"):
    assert deps.agent_runs.acquire_run_lock(
        run_id=run["id"], lock_token=token, ttl_seconds=30
    )
    deps.agent_runs.update_agent_run(run_id=run["id"], status="running", error=None)
    return deps.agent_runs.get_agent_run(run_id=run["id"]), token


def _commit_effect(deps, run, action, spec, *, token: str = "worker-a", now=None):
    leased_run, lock_token = _execution_lease(deps, run, token=token)
    return commit_pre_effect_authorization(
        deps=deps,
        run=leased_run,
        action=action,
        spec=spec,
        executable_inputs=action["inputs"],
        lock_token=lock_token,
        now=now,
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
        job = _matching_validation_job(deps, approved["action"])
        return {"validation_job_id": job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )

    assert calls == 1
    assert result.action is not None
    assert result.action["status"] == "executed"
    assert result.action["receipt_id"].startswith("validation-job:")
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


def test_approval_persists_and_executes_one_normalized_payload(tmp_path, monkeypatch):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    normalized = approved["action"]["inputs"]
    assert normalized == {
        "experiment_id": "experiment-a",
        "provider": "openrouter",
        "mode": "in_app_byok",
        "auto_run": True,
        "variant_selection": "top_1",
        "prompt_version": "v1",
    }
    assert approved["action"]["inputs_hash"] == hash_payload(normalized)
    executed_inputs = None

    def _effect(*, inputs, **kwargs):
        nonlocal executed_inputs
        executed_inputs = inputs
        job = _matching_validation_job(deps, approved["action"])
        return {"validation_job_id": job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    assert executed_inputs == normalized
    assert hash_payload(executed_inputs) == approved["action"]["inputs_hash"]


def test_same_version_live_registry_semantic_drift_fails_closed(tmp_path, monkeypatch):
    deps, run, action, spec = _run_and_action(tmp_path)
    monkeypatch.setitem(spec.default_inputs, "provider", "substituted-provider")
    monkeypatch.setitem(spec.default_inputs, "auto_run", False)

    with pytest.raises(ApprovalLedgerError) as exc:
        _approve(deps, run, action)

    assert exc.value.code == "approval_registry_mismatch"
    assert "runtime_executable_contract" in str(exc.value)


def test_post_approval_live_registry_semantic_drift_cannot_reach_effect(
    tmp_path, monkeypatch
):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    monkeypatch.setitem(spec.default_inputs, "provider", "substituted-provider")
    monkeypatch.setitem(spec.default_inputs, "auto_run", False)
    effect_called = False

    def _effect(**kwargs):
        nonlocal effect_called
        effect_called = True
        return {"validation_job_id": "should-not-exist"}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )

    with pytest.raises(AgentRuntimeError, match="runtime_executable_contract"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    assert effect_called is False


def test_normal_completion_rejects_nonexistent_provider_receipt(tmp_path, monkeypatch):
    deps, run, action, _ = _run_and_action(tmp_path)
    _approve(deps, run, action)

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **kwargs: {"validation_job_id": "job-does-not-exist"},
    )

    with pytest.raises(
        AgentRuntimeError, match="no tenant-scoped durable provider job"
    ):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    effect = deps.approval_ledger.get_effect_execution(
        tenant_id="client-a",
        workflow_id=run["id"],
        effect_idempotency_key=action["dedupe_key"],
    )
    assert effect["status"] == "uncertain"
    assert (
        deps.validation_jobs.get_job(job_id="job-does-not-exist", client_id="client-a")
        is None
    )


def test_normal_completion_rejects_matching_historical_provider_job(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)
    historical = _matching_validation_job(deps, approved["action"], bind_effect=False)
    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        lambda **kwargs: {"validation_job_id": historical["id"]},
    )

    with pytest.raises(AgentRuntimeError, match="approved executable payload"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    assert effect["status"] == "uncertain"
    assert historical["approval_effect_execution_id"] is None


def test_coordinated_preapproval_identity_substitution_fails_registry_oracle(tmp_path):
    deps, run, action, _ = _run_and_action(tmp_path)
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_actions
        SET tool_id = 'harmless.read_only', effect_class = 'recommend'
        WHERE id = ?
        """,
        (action["id"],),
    )
    conn.commit()

    with pytest.raises(ApprovalLedgerError) as exc:
        _approve(
            deps,
            run,
            deps.agent_actions.get_agent_action(action_id=action["id"]),
        )

    assert exc.value.code == "approval_registry_mismatch"
    assert (
        deps.approval_ledger.get_current_approval_for_action(
            tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
        )
        is None
    )


def test_coordinated_preapproval_registry_substitution_requires_a_real_payload(
    tmp_path,
):
    deps, run, action, _ = _run_and_action(tmp_path)
    conn = get_connection()
    substituted_fingerprint = "b" * 64
    conn.execute(
        "UPDATE agent_runs SET registry_fingerprint = ? WHERE id = ?",
        (substituted_fingerprint, run["id"]),
    )
    conn.execute(
        "UPDATE agent_actions SET registry_fingerprint = ? WHERE id = ?",
        (substituted_fingerprint, action["id"]),
    )
    conn.commit()

    with pytest.raises(ApprovalLedgerError) as exc:
        _approve(
            deps,
            deps.agent_runs.get_agent_run(run_id=run["id"]),
            deps.agent_actions.get_agent_action(action_id=action["id"]),
        )

    assert exc.value.code == "approval_registry_mismatch"
    assert "fingerprint" in str(exc.value)


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
            "input_hash",
        ),
        (
            "UPDATE agent_actions SET rationale_text = ?",
            ("different evidence",),
            "evidence_digest",
        ),
        (
            "UPDATE agent_actions SET capability_name = ?",
            ("seed_hypotheses",),
            "runtime_capability_name",
        ),
        (
            "UPDATE agent_actions SET capability_version = ?",
            ("v2",),
            "capability_version",
        ),
        (
            "UPDATE agent_actions SET tool_id = ?",
            ("experiment.run_variant",),
            "tool_id",
        ),
        ("UPDATE agent_actions SET tool_version = ?", ("v2",), "tool_version"),
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
        approving_authority=approval_authority(),
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
        approving_authority=approval_authority(),
        idempotency_key="request-replacement",
    )
    superseded = issue_action_approval_command(
        deps=deps,
        run=run,
        action=source["action"],
        command_type="supersede",
        approval_id=source["approval"]["approval_id"],
        supersession_reference=replacement["approval"]["approval_id"],
        approving_authority=approval_authority(),
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
            approving_authority=approval_authority(),
            idempotency_key="race-revocation-wins",
            revocation_reference="operator-stop",
        )
        return original(**kwargs)

    monkeypatch.setattr(
        deps.approval_ledger, "commit_effect_authorization", _revoke_first
    )

    with pytest.raises(ApprovalAuthorizationError) as exc:
        _commit_effect(deps, run, executing, spec)

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
    authorization = _commit_effect(deps, run, executing, spec)
    assert authorization is not None

    with pytest.raises(ApprovalLedgerError) as exc:
        issue_action_approval_command(
            deps=deps,
            run=run,
            action=executing,
            command_type="revoke",
            approval_id=approved["approval"]["approval_id"],
            approving_authority=approval_authority(),
            idempotency_key="race-effect-wins",
            revocation_reference="too-late",
        )

    assert exc.value.code == "effect_already_started"


def test_cancellation_committed_before_effect_start_fails_closed(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    leased_run, token = _execution_lease(deps, run)
    deps.agent_runs.update_agent_run(run_id=run["id"], status="canceled", error=None)

    with pytest.raises(ApprovalAuthorizationError) as exc:
        commit_pre_effect_authorization(
            deps=deps,
            run=leased_run,
            action=executing,
            spec=spec,
            executable_inputs=executing["inputs"],
            lock_token=token,
        )

    assert exc.value.code == "approval_changed_before_effect"
    assert (
        deps.approval_ledger.get_effect_execution(
            tenant_id="client-a",
            workflow_id=run["id"],
            effect_idempotency_key=executing["dedupe_key"],
        )
        is None
    )


def test_stale_worker_token_cannot_commit_an_effect(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    leased_run, stale_token = _execution_lease(deps, run, token="stale-worker")
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_runs
        SET lock_token = 'current-worker',
            lock_expires_at = datetime('now', '+30 seconds')
        WHERE id = ?
        """,
        (run["id"],),
    )
    conn.commit()

    with pytest.raises(ApprovalAuthorizationError) as exc:
        commit_pre_effect_authorization(
            deps=deps,
            run=leased_run,
            action=executing,
            spec=spec,
            executable_inputs=executing["inputs"],
            lock_token=stale_token,
        )

    assert exc.value.code == "approval_changed_before_effect"


def test_pre_effect_start_atomically_reserves_shared_action_budget(tmp_path):
    deps, run, first_action, spec = _run_and_action(tmp_path)
    conn = get_connection()
    conn.execute(
        "UPDATE agent_runs SET budgets_json = json(?) WHERE id = ?",
        (json.dumps({"max_actions": 1}), run["id"]),
    )
    conn.commit()
    run = deps.agent_runs.get_agent_run(run_id=run["id"])
    _approve(deps, run, first_action)
    first = deps.agent_actions.transition_agent_action_status(
        action_id=first_action["id"], from_status="approved", to_status="executing"
    )
    first_start = _commit_effect(deps, run, first, spec, token="worker-one")
    assert first_start is not None

    second = _additional_action(deps, run, spec)
    _approve(deps, run, second)
    second = deps.agent_actions.transition_agent_action_status(
        action_id=second["id"], from_status="approved", to_status="executing"
    )
    conn.execute(
        "UPDATE agent_runs SET lock_expires_at = datetime('now', '-1 second') WHERE id = ?",
        (run["id"],),
    )
    conn.commit()

    with pytest.raises(ApprovalAuthorizationError) as exc:
        _commit_effect(deps, run, second, spec, token="worker-two")

    assert exc.value.code == "effect_budget_exhausted"
    starts = conn.execute(
        "SELECT COUNT(*) FROM approval_effect_executions WHERE workflow_id = ?",
        (run["id"],),
    ).fetchone()[0]
    assert starts == 1


def test_effect_identity_and_outcome_state_cannot_be_rewritten(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)
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
    with pytest.raises(sqlite3.IntegrityError, match="snapshot is immutable"):
        conn.execute(
            """
            UPDATE approval_effect_executions
            SET authorization_snapshot_json = json(?),
                authorization_snapshot_digest = ?,
                status = 'uncertain', error_code = 'tampered'
            WHERE execution_id = ?
            """,
            (json.dumps({"tampered": True}), "f" * 64, authorization.execution_id),
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
    authorization = _commit_effect(deps, run, executing, spec)
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

    job = _matching_validation_job(deps, executing)
    outputs = {"validation_job_id": job["id"]}
    receipt_id = f"validation-job:{job['id']}"
    reloaded_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    reloaded_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    reconciled = reconcile_authorized_effect(
        deps=deps,
        run=reloaded_run,
        action=reloaded_action,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=receipt_id,
    )

    assert reconciled["status"] == "succeeded"
    persisted = deps.agent_actions.get_agent_action(action_id=action["id"])
    assert persisted["status"] == "executed"
    assert persisted["receipt_id"] == receipt_id

    duplicate = reconcile_authorized_effect(
        deps=deps,
        run=deps.agent_runs.get_agent_run(run_id=run["id"]),
        action=persisted,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=receipt_id,
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
    assert exc.value.code == "effect_receipt_unverifiable"


def test_receipt_started_while_valid_reconciles_after_approval_expiry(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    decided_at = datetime.now(timezone.utc)
    issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type="approve",
        approving_authority=approval_authority(),
        idempotency_key="approve-short-lived-effect",
        occurred_at=decided_at,
        ttl_seconds=1,
    )
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(
        deps,
        run,
        executing,
        spec,
        now=decided_at + timedelta(milliseconds=500),
    )
    assert authorization is not None
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=executing,
        authorization=authorization,
        error_code="receipt_delayed",
        now=decided_at + timedelta(milliseconds=750),
    )
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="receipt delayed"
    )
    job = _matching_validation_job(deps, executing)
    outputs = {"validation_job_id": job["id"]}

    reconciled = reconcile_authorized_effect(
        deps=deps,
        run=deps.agent_runs.get_agent_run(run_id=run["id"]),
        action=deps.agent_actions.get_agent_action(action_id=action["id"]),
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=f"validation-job:{job['id']}",
        now=decided_at + timedelta(seconds=2),
    )

    assert reconciled["status"] == "succeeded"


def test_reconciliation_uses_immutable_start_after_current_policy_mutation(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)
    assert authorization is not None
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=executing,
        authorization=authorization,
        error_code="receipt_delayed",
    )
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="receipt delayed"
    )
    job = _matching_validation_job(deps, executing)
    outputs = {"validation_job_id": job["id"]}
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_runs
        SET policy_profile_id = 'observe',
            principal_id = 'internal-agent:substituted'
        WHERE id = ?
        """,
        (run["id"],),
    )
    conn.execute(
        """
        UPDATE agent_actions
        SET inputs_json = json(?), inputs_hash = ?, dedupe_key = ?,
            capability_name = 'review_validation_readiness',
            tool_id = 'validation.review_readiness', effect_class = 'recommend'
        WHERE id = ?
        """,
        (
            json.dumps({"experiment_id": "mutable-current-projection"}),
            hash_payload({"experiment_id": "mutable-current-projection"}),
            "mutated-current-effect-key",
            action["id"],
        ),
    )
    conn.commit()

    reconciled = reconcile_authorized_effect(
        deps=deps,
        run=deps.agent_runs.get_agent_run(run_id=run["id"]),
        action=deps.agent_actions.get_agent_action(action_id=action["id"]),
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=f"validation-job:{job['id']}",
    )

    assert reconciled["status"] == "succeeded"
    assert reconciled["receipt_id"] == f"validation-job:{job['id']}"
    completion_events = [
        event
        for event in deps.agent_events.list_agent_events(agent_run_id=run["id"])
        if event["event_type"]
        in {"approval_effect_succeeded", "approval_fulfilled", "action_executed"}
    ]
    assert len(completion_events) == 3
    for event in completion_events:
        assert event["principal_id"] == "internal-agent:planner-a"
        assert event["capability_name"] == "request_synthetic_validation"
        assert event["capability_version"] == "v1"
        assert event["tool_id"] == "validation.request_synthetic"
        assert event["effect_class"] == "external_side_effect"


@pytest.mark.parametrize(
    ("outputs_factory", "hash_factory", "expected_code"),
    [
        (
            lambda job_id: {},
            lambda outputs: hash_payload(outputs),
            "effect_output_invalid",
        ),
        (
            lambda job_id: {"validation_job_id": job_id},
            lambda outputs: hash_payload({"different": "content"}),
            "effect_output_hash_mismatch",
        ),
    ],
)
def test_reconciliation_rejects_malformed_or_mishashed_outputs(
    tmp_path, outputs_factory, hash_factory, expected_code
):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)
    assert authorization is not None
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=executing,
        authorization=authorization,
        error_code="provider_timeout",
    )
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="provider timeout"
    )
    job = _matching_validation_job(deps, executing)
    outputs = outputs_factory(job["id"])

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=deps.agent_runs.get_agent_run(run_id=run["id"]),
            action=deps.agent_actions.get_agent_action(action_id=action["id"]),
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_factory(outputs),
            receipt_id=f"validation-job:{job['id']}",
        )

    assert exc.value.code == expected_code
    execution = deps.approval_ledger.get_effect_execution(
        tenant_id="client-a",
        workflow_id=run["id"],
        effect_idempotency_key=executing["dedupe_key"],
    )
    assert execution["status"] == "uncertain"


def test_reconciliation_rejects_provider_job_from_different_approved_target(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)
    assert authorization is not None
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=executing,
        authorization=authorization,
        error_code="provider_timeout",
    )
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="provider timeout"
    )
    wrong_job = _matching_validation_job(
        deps, executing, entity_id="different-experiment"
    )
    outputs = {"validation_job_id": wrong_job["id"]}

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=deps.agent_runs.get_agent_run(run_id=run["id"]),
            action=deps.agent_actions.get_agent_action(action_id=action["id"]),
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{wrong_job['id']}",
        )

    assert exc.value.code == "effect_receipt_provenance_mismatch"
    assert "entity_id" in exc.value.mismatches


def test_same_effect_identity_cannot_be_reused_by_a_second_action(tmp_path):
    deps, run, action, spec = _run_and_action(tmp_path)
    _approve(deps, run, action)
    first = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    _commit_effect(deps, run, first, spec)

    second = _additional_action(deps, run, spec, dedupe_key="effect:validation:1")
    approved_second = _approve(deps, run, second)
    second_executing = deps.agent_actions.transition_agent_action_status(
        action_id=second["id"], from_status="approved", to_status="executing"
    )

    with pytest.raises(ApprovalAuthorizationError) as exc:
        _commit_effect(deps, run, second_executing, spec)

    assert exc.value.code == "effect_identity_conflict"
    assert approved_second["approval"]["status"] == "approved"
