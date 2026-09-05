from __future__ import annotations

import json
import sqlite3
import uuid

import pytest

from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.capabilities import CapabilityExecutionError
from application.services.agent_runtime.commands import issue_agent_run_command
from application.services.agent_runtime.runtime import AgentRuntimeService
from application.services.agent_runtime.runtime.payloads import hash_payload
from shared.db.connection import get_connection
from tests.modules.approval_effect_support import approval_authority
from tests.modules.test_approval_effect_authorization import (
    _approve,
    _commit_effect,
    _run_and_action,
)


def _lab_action(tmp_path):
    deps, run, action, spec = _run_and_action(
        tmp_path,
        capability_name="promote_variant_lab",
        dedupe_key="effect:lab-promotion:1",
    )
    deps.clients.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    deps.clients.create_product(
        product_id="product-a", brand_id="brand-a", name="Product A"
    )
    experiment = deps.experiments.create_experiment(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        name="Lab promotion",
    )
    variant = deps.experiments.add_variant(
        experiment_id=experiment["id"],
        client_id="client-a",
        label="Candidate A",
        variant_type="candidate",
        payload={"description": "Candidate"},
    )
    metric = deps.experiment_runs.create_metric(
        experiment_id=experiment["id"],
        variant_id=variant["id"],
        metrics={
            "decision_action": "promote_variant",
            "decision_tier": "lab",
            "posterior": 0.84,
            "decision_policy_version": "test-v1",
        },
    )
    inputs = {
        "experiment_id": experiment["id"],
        "variant_id": variant["id"],
        "reason": "Reviewed lab promotion",
    }
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_actions
        SET inputs_json = json(?), inputs_hash = NULL, variant_id = ?
        WHERE id = ?
        """,
        (json.dumps(inputs), variant["id"], action["id"]),
    )
    conn.commit()
    action = deps.agent_actions.get_agent_action(action_id=action["id"])
    return deps, run, action, spec, experiment, variant, metric


def _cross_tenant_lab_action(tmp_path):
    deps, run, action, spec = _run_and_action(
        tmp_path,
        capability_name="promote_variant_lab",
        dedupe_key="effect:cross-tenant-lab-promotion:1",
    )
    deps.clients.create_brand(brand_id="brand-a", client_id="client-a", name="Brand A")
    deps.clients.create_product(
        product_id="product-a", brand_id="brand-a", name="Product A"
    )
    experiment_a = deps.experiments.create_experiment(
        client_id="client-a",
        brand_id="brand-a",
        product_id="product-a",
        name="Tenant A experiment",
    )
    deps.clients.create_client(client_id="client-b", name="Client B")
    deps.clients.create_brand(brand_id="brand-b", client_id="client-b", name="Brand B")
    deps.clients.create_product(
        product_id="product-b", brand_id="brand-b", name="Product B"
    )
    experiment_b = deps.experiments.create_experiment(
        client_id="client-b",
        brand_id="brand-b",
        product_id="product-b",
        name="Tenant B experiment",
    )
    variant_b = deps.experiments.add_variant(
        experiment_id=experiment_b["id"],
        client_id="client-b",
        label="Tenant B candidate",
        variant_type="candidate",
        payload={"description": "Tenant B candidate"},
    )
    cross_linked_metric = deps.experiment_runs.create_metric(
        experiment_id=experiment_a["id"],
        variant_id=variant_b["id"],
        metrics={
            "decision_action": "promote_variant",
            "decision_tier": "lab",
            "posterior": 0.91,
            "decision_policy_version": "test-v1",
        },
    )
    inputs = {
        "experiment_id": experiment_a["id"],
        "variant_id": variant_b["id"],
        "reason": "Attempt a cross-tenant promotion",
    }
    conn = get_connection()
    conn.execute(
        """
        UPDATE agent_actions
        SET inputs_json = json(?), inputs_hash = NULL, variant_id = ?
        WHERE id = ?
        """,
        (json.dumps(inputs), variant_b["id"], action["id"]),
    )
    conn.commit()
    return (
        deps,
        run,
        deps.agent_actions.get_agent_action(action_id=action["id"]),
        spec,
        experiment_a,
        variant_b,
        cross_linked_metric,
    )


def _assert_no_lab_promotion_projection(deps) -> None:
    assert deps.analytics_events.list_events(client_id="client-a") == []
    assert deps.decision_events.list_decision_events(client_id="client-a") == []
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM governed_effect_receipts")
        .fetchone()[0]
        == 0
    )


def _commit_with_previous_lab_writer(
    *, deps, run, action, approval_id, execution_id, experiment, variant, metric
):
    analytics_event_id = str(uuid.uuid4())
    decision_event_id = str(uuid.uuid4())
    reason = action["inputs"]["reason"]
    metric_payload = metric["metrics"]
    posterior = metric_payload["posterior"]
    outputs = {
        "experiment_id": experiment["id"],
        "variant_id": variant["id"],
        "promotion_tier": "lab",
        "reason": reason,
        "source_metric_id": metric["id"],
        "posterior": posterior,
        "decision_action": metric_payload["decision_action"],
        "decision_tier": metric_payload["decision_tier"],
        "decision_policy_version": metric_payload["decision_policy_version"],
        "analytics_event_id": analytics_event_id,
        "decision_event_id": decision_event_id,
        "status": "variant_promoted_lab",
    }
    conn = get_connection()
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            """
            INSERT INTO analytics_events (
                id, client_id, brand_id, product_id, variant_id, experiment_id,
                event_type, source, metadata_json
            ) VALUES (?, 'client-a', ?, ?, ?, ?,
                      'variant_promoted_lab', 'agent_runtime', json(?))
            """,
            (
                analytics_event_id,
                experiment["brand_id"],
                experiment["product_id"],
                variant["id"],
                experiment["id"],
                json.dumps({"metric_id": metric["id"], "reason": reason}),
            ),
        )
        conn.execute(
            """
            INSERT INTO decision_events (
                id, client_id, brand_id, product_id, policy_action,
                uncertainty, expected_gain, selected_reason
            ) VALUES (?, 'client-a', ?, ?, 'promote_variant_lab', ?, ?, ?)
            """,
            (
                decision_event_id,
                experiment["brand_id"],
                experiment["product_id"],
                1.0 - posterior,
                posterior,
                reason,
            ),
        )
        # Exact column list used by the immediately preceding a0be38e writer.
        conn.execute(
            """
            INSERT INTO governed_effect_receipts (
                receipt_id, tenant_id, workflow_id, action_id, approval_id,
                effect_idempotency_key, approval_effect_execution_id,
                capability_name, analytics_event_id, decision_event_id,
                outputs_json, outputs_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'promote_variant_lab', ?, ?, json(?), ?)
            """,
            (
                f"lab-promotion:{execution_id}",
                "client-a",
                run["id"],
                action["id"],
                approval_id,
                action["dedupe_key"],
                execution_id,
                analytics_event_id,
                decision_event_id,
                json.dumps(outputs),
                hash_payload(outputs),
            ),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return outputs


def test_lab_promotion_commits_effect_and_receipt_atomically(tmp_path):
    deps, run, action, _, experiment, variant, metric = _lab_action(tmp_path)
    approved = _approve(deps, run, action)

    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )

    assert result.action is not None
    assert result.action["status"] == "executed"
    outputs = result.action["outputs"]
    assert outputs["experiment_id"] == experiment["id"]
    assert outputs["variant_id"] == variant["id"]
    assert outputs["source_metric_id"] == metric["id"]
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    receipt = deps.governed_effect_receipts.get_receipt_for_effect_execution(
        approval_effect_execution_id=execution["execution_id"], tenant_id="client-a"
    )
    assert execution["status"] == "succeeded"
    assert execution["receipt_id"] == receipt["receipt_id"]
    assert receipt["outputs"] == outputs
    assert receipt["outputs_hash"] == hash_payload(outputs)
    assert approved["approval"]["approval_id"] == receipt["approval_id"]
    assert deps.analytics_events.get_event(outputs["analytics_event_id"]) is not None
    assert (
        deps.decision_events.get_decision_event(event_id=outputs["decision_event_id"])
        is not None
    )


def test_migration_048_accepts_previous_writer_for_valid_scoped_promotion(tmp_path):
    deps, run, action, spec, experiment, variant, metric = _lab_action(tmp_path)
    approved = _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)
    _commit_with_previous_lab_writer(
        deps=deps,
        run=run,
        action=action,
        approval_id=approved["approval"]["approval_id"],
        execution_id=authorization.execution_id,
        experiment=experiment,
        variant=variant,
        metric=metric,
    )

    receipt = deps.governed_effect_receipts.get_receipt_for_effect_execution(
        approval_effect_execution_id=authorization.execution_id,
        tenant_id="client-a",
    )
    assert receipt is not None
    assert receipt["scope_status"] == "validated"
    assert receipt["source_metric_id"] == metric["id"]


def test_migration_048_previous_writer_still_rejects_cross_tenant_scope(tmp_path):
    deps, run, action, spec, experiment, variant, metric = _cross_tenant_lab_action(
        tmp_path
    )
    approved = _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)

    with pytest.raises(
        sqlite3.IntegrityError, match="governed effect receipt scope is invalid"
    ):
        _commit_with_previous_lab_writer(
            deps=deps,
            run=run,
            action=action,
            approval_id=approved["approval"]["approval_id"],
            execution_id=authorization.execution_id,
            experiment=experiment,
            variant=variant,
            metric=metric,
        )

    _assert_no_lab_promotion_projection(deps)


def test_lab_promotion_rejects_cross_tenant_variant_before_effect(tmp_path):
    deps, run, action, _, _, _, _ = _cross_tenant_lab_action(tmp_path)
    _approve(deps, run, action)

    with pytest.raises(
        CapabilityExecutionError,
        match="variant does not belong to the tenant-scoped experiment",
    ):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    _assert_no_lab_promotion_projection(deps)


def test_lab_promotion_commit_revalidates_tenant_variant_metric_scope(tmp_path):
    deps, run, action, spec, experiment, variant, metric = _cross_tenant_lab_action(
        tmp_path
    )
    approved = _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)

    with pytest.raises(
        ValueError,
        match="experiment, variant, and metric scope is invalid",
    ):
        deps.governed_effect_receipts.commit_lab_promotion(
            tenant_id="client-a",
            workflow_id=run["id"],
            action_id=action["id"],
            approval_id=approved["approval"]["approval_id"],
            effect_idempotency_key=action["dedupe_key"],
            approval_effect_execution_id=authorization.execution_id,
            experiment_id=experiment["id"],
            variant_id=variant["id"],
            reason=action["inputs"]["reason"],
            source_metric_id=metric["id"],
        )

    _assert_no_lab_promotion_projection(deps)


def test_lab_promotion_write_failure_rolls_back_events_and_receipt(
    tmp_path, monkeypatch
):
    deps, run, action, _, _, _, _ = _lab_action(tmp_path)
    _approve(deps, run, action)
    conn = get_connection()
    conn.execute(
        """
        CREATE TRIGGER reject_test_lab_decision
        BEFORE INSERT ON decision_events
        WHEN NEW.policy_action = 'promote_variant_lab'
        BEGIN
            SELECT RAISE(ABORT, 'injected decision failure');
        END
        """
    )
    conn.commit()

    with pytest.raises(
        CapabilityExecutionError, match="lab-promotion effect commit conflicted"
    ):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    assert deps.analytics_events.list_events(client_id="client-a") == []
    assert deps.decision_events.list_decision_events(client_id="client-a") == []
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM governed_effect_receipts")
        .fetchone()[0]
        == 0
    )


def test_lab_promotion_recovers_from_durable_receipt_without_reexecution(
    tmp_path, monkeypatch
):
    deps, run, action, _, _, _, _ = _lab_action(tmp_path)
    _approve(deps, run, action)
    from application.services.agent_runtime.runtime import authorized_execution

    original_completion = authorized_execution.complete_authorized_effect

    def _lose_local_completion(**kwargs):
        raise RuntimeError("injected process loss after durable lab commit")

    monkeypatch.setattr(
        authorized_execution, "complete_authorized_effect", _lose_local_completion
    )
    with pytest.raises(CapabilityExecutionError, match="injected process loss"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")
    monkeypatch.setattr(
        authorized_execution, "complete_authorized_effect", original_completion
    )

    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    assert execution["status"] == "uncertain"
    receipt_count = (
        get_connection()
        .execute("SELECT COUNT(*) FROM governed_effect_receipts")
        .fetchone()[0]
    )

    recovered = issue_agent_run_command(
        deps=deps,
        runtime=AgentRuntimeService(deps=deps),
        run_id=run["id"],
        client_id="client-a",
        user_id="operator-a",
        command_type="reconcile_effect",
        action_id=action["id"],
        message="Reconcile the durable lab receipt",
        metadata={},
        approving_authority=approval_authority(),
    )

    assert recovered["effect_execution"]["status"] == "succeeded"
    assert recovered["action"]["status"] == "executed"
    assert recovered["governed_effect_receipt"]["receipt_id"].startswith(
        "lab-promotion:"
    )
    assert (
        get_connection()
        .execute("SELECT COUNT(*) FROM governed_effect_receipts")
        .fetchone()[0]
        == receipt_count
    )
    assert len(deps.analytics_events.list_events(client_id="client-a")) == 1
    assert len(deps.decision_events.list_decision_events(client_id="client-a")) == 1


def test_lab_promotion_reconciliation_rejects_substituted_outputs(
    tmp_path, monkeypatch
):
    deps, run, action, spec, _, _, _ = _lab_action(tmp_path)
    _approve(deps, run, action)
    from application.services.agent_runtime.runtime import authorized_execution

    def _lose_local_completion(**kwargs):
        raise RuntimeError("injected process loss")

    monkeypatch.setattr(
        authorized_execution, "complete_authorized_effect", _lose_local_completion
    )
    with pytest.raises(CapabilityExecutionError):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")
    failed_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    receipt = deps.governed_effect_receipts.get_receipt_for_effect_execution(
        approval_effect_execution_id=execution["execution_id"], tenant_id="client-a"
    )
    substituted = dict(receipt["outputs"])
    substituted["variant_id"] = "substituted-variant"

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=failed_run,
            action=failed_action,
            spec=spec,
            outputs=substituted,
            outputs_hash=hash_payload(substituted),
            receipt_id=receipt["receipt_id"],
        )

    assert exc.value.code == "effect_receipt_provenance_mismatch"
    assert "outputs" in exc.value.mismatches


def test_governed_effect_receipt_is_immutable(tmp_path):
    deps, run, action, spec, _, _, _ = _lab_action(tmp_path)
    _approve(deps, run, action)
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )
    conn = get_connection()
    execution = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    receipt = deps.governed_effect_receipts.get_receipt_for_effect_execution(
        approval_effect_execution_id=execution["execution_id"], tenant_id="client-a"
    )

    deps.clients.create_client(client_id="client-b", name="Client B")
    assert (
        deps.governed_effect_receipts.get_receipt_for_effect_execution(
            approval_effect_execution_id=execution["execution_id"],
            tenant_id="client-b",
        )
        is None
    )

    with pytest.raises(sqlite3.IntegrityError, match="receipts are immutable"):
        conn.execute(
            "UPDATE governed_effect_receipts SET outputs_hash = ?",
            ("f" * 64,),
        )
    conn.rollback()
    with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
        conn.execute("DELETE FROM governed_effect_receipts")
    conn.rollback()

    conn.execute(
        "UPDATE analytics_events SET metadata_json = json(?) WHERE id = ?",
        (json.dumps({"reason": "substituted"}), receipt["analytics_event_id"]),
    )
    conn.commit()
    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=deps.agent_runs.get_agent_run(run_id=run["id"]),
            action=deps.agent_actions.get_agent_action(action_id=action["id"]),
            spec=spec,
            outputs=result.action["outputs"],
            outputs_hash=hash_payload(result.action["outputs"]),
            receipt_id=receipt["receipt_id"],
        )
    assert exc.value.code == "effect_receipt_provenance_mismatch"
    assert "analytics_event" in exc.value.mismatches
