from __future__ import annotations

import json
import sqlite3

import pytest

from application.services.agent_runtime.approval_authorization import (
    ApprovalAuthorizationError,
    mark_authorized_effect_uncertain,
    reconcile_authorized_effect,
)
from application.services.agent_runtime.capabilities import (
    CapabilityContext,
    CapabilityExecutionError,
    execute_capability,
)
from application.services.agent_runtime.runtime import (
    AgentRuntimeError,
    AgentRuntimeService,
)
from application.services.agent_runtime.runtime.payloads import hash_payload
from application.services.validation_service import ValidationService
from shared.db.connection import get_connection
from tests.modules.approval_effect_support import matching_validation_job
from tests.modules.test_approval_effect_authorization import (
    _approve,
    _commit_effect,
    _run_and_action,
)


def _uncertain_effect(tmp_path, *, auto_run: bool = True, model: str | None = None):
    deps, run, action, spec = _run_and_action(tmp_path)
    if not auto_run or model is not None:
        inputs = {"experiment_id": "experiment-a"}
        if not auto_run:
            inputs["auto_run"] = False
        if model is not None:
            inputs["model"] = model
        conn = get_connection()
        conn.execute(
            "UPDATE agent_actions SET inputs_json = json(?) WHERE id = ?",
            (json.dumps(inputs), action["id"]),
        )
        conn.commit()
        action = deps.agent_actions.get_agent_action(action_id=action["id"])
    _approve(deps, run, action)
    executing = deps.agent_actions.transition_agent_action_status(
        action_id=action["id"], from_status="approved", to_status="executing"
    )
    authorization = _commit_effect(deps, run, executing, spec)
    mark_authorized_effect_uncertain(
        deps=deps,
        run=run,
        action=executing,
        authorization=authorization,
        error_code="provider_completion_unknown",
    )
    deps.agent_actions.update_agent_action_status(
        action_id=action["id"], status="failed", error="provider outcome unknown"
    )
    return deps, run, executing, spec


@pytest.mark.parametrize("job_status", ["created", "running", "failed"])
def test_reconciliation_rejects_noncompleted_auto_run_job(tmp_path, job_status):
    deps, run, action, spec = _uncertain_effect(tmp_path)
    job = matching_validation_job(
        deps,
        action,
        status=job_status,
        with_result=job_status == "failed",
    )
    outputs = {"validation_job_id": job["id"]}

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=run,
            action=action,
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{job['id']}",
        )

    assert exc.value.code == "effect_receipt_outcome_incomplete"
    assert "validation_job_status" in exc.value.mismatches
    persisted = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    assert persisted["status"] == "uncertain"


def test_reconciliation_requires_matching_durable_auto_run_result(tmp_path):
    deps, run, action, spec = _uncertain_effect(tmp_path)
    job = matching_validation_job(deps, action, status="completed", with_result=False)
    outputs = {"validation_job_id": job["id"]}

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=run,
            action=action,
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{job['id']}",
        )

    assert exc.value.code == "effect_receipt_outcome_incomplete"
    assert "validation_result" in exc.value.mismatches

    deps.validation_results.create_result(
        job_id=job["id"],
        provider="substituted-provider",
        model=job["model"],
        structured_result={"winner_id": "variant-a", "score": 0.9},
        raw_response=None,
        score=0.9,
        winner_id="variant-a",
        evidence_strength="strong",
        latency_ms=10,
        cost_usd=None,
        source="synthetic",
        callback_verified=False,
    )
    with pytest.raises(ApprovalAuthorizationError) as mismatch:
        reconcile_authorized_effect(
            deps=deps,
            run=run,
            action=action,
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{job['id']}",
        )
    assert mismatch.value.code == "effect_receipt_provenance_mismatch"
    assert "validation_result_provider" in mismatch.value.mismatches


def test_normal_completion_rejects_failed_auto_run_job(tmp_path, monkeypatch):
    deps, run, action, _ = _run_and_action(tmp_path)
    approved = _approve(deps, run, action)

    def _failed_effect(**kwargs):
        job = matching_validation_job(
            deps, approved["action"], status="failed", with_result=False
        )
        return {"validation_job_id": job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _failed_effect
    )
    with pytest.raises(AgentRuntimeError, match="completed durable provider job"):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    assert effect["status"] == "uncertain"


def test_reconciliation_accepts_bound_queued_job_when_auto_run_is_disabled(tmp_path):
    deps, run, action, spec = _uncertain_effect(tmp_path, auto_run=False)
    job = matching_validation_job(deps, action, status="queued", with_result=False)
    outputs = {"validation_job_id": job["id"]}

    reconciled = reconcile_authorized_effect(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
        receipt_id=f"validation-job:{job['id']}",
    )

    assert reconciled["status"] == "succeeded"


def test_approval_canonicalizes_payload_before_effect_start(tmp_path, monkeypatch):
    deps, run, action, _ = _run_and_action(tmp_path)
    raw_inputs = {
        "experiment_id": " experiment-a ",
        "provider": " OPENROUTER ",
        "mode": " IN_APP_BYOK ",
        "model": " approved-model ",
        "prompt_version": " v1 ",
        "variant_selection": " TOP_1 ",
        "auto_run": True,
    }
    conn = get_connection()
    conn.execute(
        "UPDATE agent_actions SET inputs_json = json(?) WHERE id = ?",
        (json.dumps(raw_inputs), action["id"]),
    )
    conn.commit()
    action = deps.agent_actions.get_agent_action(action_id=action["id"])
    approved = _approve(deps, run, action)
    canonical = approved["action"]["inputs"]
    assert canonical["model"] == "approved-model"
    assert canonical["provider"] == "openrouter"
    assert canonical["mode"] == "in_app_byok"
    assert canonical["experiment_id"] == "experiment-a"
    assert canonical["prompt_version"] == "v1"
    assert canonical["variant_selection"] == "top_1"
    assert approved["action"]["inputs_hash"] == hash_payload(canonical)
    consumed_inputs = None

    def _effect(*, inputs, **kwargs):
        nonlocal consumed_inputs
        consumed_inputs = inputs
        job = matching_validation_job(deps, approved["action"])
        return {"validation_job_id": job["id"]}

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability", _effect
    )
    result = AgentRuntimeService(deps=deps).step_once(
        run_id=run["id"], user_id="operator-a"
    )

    assert consumed_inputs == canonical
    assert result.action["status"] == "executed"


def test_unexpected_post_start_failure_is_recoverable_not_stranded(
    tmp_path, monkeypatch
):
    deps, run, action, _ = _run_and_action(tmp_path)
    _approve(deps, run, action)

    def _persistence_failure(**kwargs):
        raise sqlite3.IntegrityError("simulated provider receipt constraint")

    monkeypatch.setattr(
        "application.services.agent_runtime.runtime.execute_capability",
        _persistence_failure,
    )

    with pytest.raises(
        CapabilityExecutionError, match="simulated provider receipt constraint"
    ):
        AgentRuntimeService(deps=deps).step_once(run_id=run["id"], user_id="operator-a")

    effect = deps.approval_ledger.get_effect_execution_for_action(
        tenant_id="client-a", workflow_id=run["id"], action_id=action["id"]
    )
    failed_action = deps.agent_actions.get_agent_action(action_id=action["id"])
    failed_run = deps.agent_runs.get_agent_run(run_id=run["id"])
    assert effect["status"] == "uncertain"
    assert failed_action["status"] == "failed"
    assert failed_run["status"] == "failed"


def test_governed_capability_consumes_canonical_strings_without_rewriting(
    tmp_path, monkeypatch
):
    deps, _, _, spec = _run_and_action(tmp_path)
    canonical = spec.normalize_inputs(
        {
            "experiment_id": " experiment-a ",
            "provider": " OPENROUTER ",
            "mode": " IN_APP_BYOK ",
            "model": " approved-model ",
            "prompt_version": " v1 ",
            "variant_id": " variant-a ",
            "variant_selection": " TOP_1 ",
            "auto_run": False,
        }
    )
    captured = None

    class _ValidationService:
        def create_job(self, **kwargs):
            nonlocal captured
            captured = kwargs
            return {"id": "job-a", "status": "created"}

    monkeypatch.setattr(
        "application.services.agent_runtime.capabilities.executor.ValidationService",
        lambda **kwargs: _ValidationService(),
    )
    monkeypatch.setattr(
        "application.services.agent_runtime.capabilities.executor._build_experiment_validation_payload",
        lambda **kwargs: {"experiment": {}},
    )
    context = CapabilityContext(
        client_id="client-a",
        user_id="operator-a",
        approval_effect_execution_id="effect-a",
    )

    execute_capability(
        deps=deps,
        context=context,
        capability_name=spec.name,
        inputs=canonical,
    )

    assert captured["entity_id"] == canonical["experiment_id"]
    assert captured["provider"] == canonical["provider"]
    assert captured["mode"] == canonical["mode"]
    assert captured["model"] == canonical["model"]
    assert captured["prompt_version"] == canonical["prompt_version"]
    with pytest.raises(CapabilityExecutionError, match="non-canonical inputs"):
        execute_capability(
            deps=deps,
            context=context,
            capability_name=spec.name,
            inputs={**canonical, "model": " approved-model "},
        )


def test_coordinated_job_result_model_substitution_cannot_fulfill_approval(tmp_path):
    deps, run, action, spec = _uncertain_effect(tmp_path, model="approved-model")
    with pytest.raises(sqlite3.IntegrityError, match="does not match effect start"):
        matching_validation_job(
            deps,
            action,
            status="completed",
            with_result=False,
            model_override="substituted-expensive-model",
        )
    get_connection().rollback()

    job = matching_validation_job(deps, action, status="completed", with_result=True)
    conn = get_connection()
    conn.execute(
        "UPDATE validation_jobs SET model = ? WHERE id = ?",
        ("substituted-expensive-model", job["id"]),
    )
    conn.execute(
        "UPDATE validation_results SET model = ? WHERE job_id = ?",
        ("substituted-expensive-model", job["id"]),
    )
    conn.commit()
    persisted_job = deps.validation_jobs.get_job(job_id=job["id"], client_id="client-a")
    assert persisted_job["requested_model"] == "approved-model"
    outputs = {"validation_job_id": job["id"]}

    with pytest.raises(ApprovalAuthorizationError) as exc:
        reconcile_authorized_effect(
            deps=deps,
            run=run,
            action=action,
            spec=spec,
            outputs=outputs,
            outputs_hash=hash_payload(outputs),
            receipt_id=f"validation-job:{job['id']}",
        )

    assert exc.value.code == "effect_receipt_provenance_mismatch"
    assert "validation_result_model" in exc.value.mismatches
    with pytest.raises(sqlite3.IntegrityError, match="requested model are immutable"):
        conn.execute(
            "UPDATE validation_jobs SET requested_model = ? WHERE id = ?",
            ("substituted-expensive-model", job["id"]),
        )
    conn.rollback()


def test_governed_auto_run_uses_immutable_requested_model(tmp_path, monkeypatch):
    deps, _, action, _ = _uncertain_effect(tmp_path, model="approved-model")
    job = matching_validation_job(deps, action, status="created", with_result=False)
    conn = get_connection()
    conn.execute(
        "UPDATE validation_jobs SET model = ? WHERE id = ?",
        ("substituted-expensive-model", job["id"]),
    )
    conn.commit()
    observed_model = None

    def _provider_response(*, prompt, provider, model):
        nonlocal observed_model
        observed_model = model
        return json.dumps(
            {
                "winner_id": "variant-a",
                "score": 0.9,
                "confidence": 0.8,
                "evidence_strength": "strong",
            }
        )

    monkeypatch.setattr(
        "application.services.validation_service._run_validation_prompt",
        _provider_response,
    )
    completed = ValidationService(deps=deps).run_job(job_id=job["id"])

    assert observed_model == "approved-model"
    assert completed["result"]["model"] == "approved-model"
