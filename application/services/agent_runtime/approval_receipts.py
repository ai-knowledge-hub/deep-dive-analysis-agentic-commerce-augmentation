"""Independent evidence checks for all governed-effect completions."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_registry import (
    ApprovalRegistryError,
    capability_spec_from_contract_json,
)
from application.services.agent_runtime.registry import validate_outputs
from domain.workflow.approval import ApprovalBinding


class ApprovalReceiptError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        mismatches: tuple[str, ...] = (),
    ) -> None:
        super().__init__(message)
        self.code = code
        self.mismatches = mismatches


@dataclass(frozen=True)
class VerifiedEffectReceipt:
    receipt_id: str
    outputs_hash: str


def verify_effect_receipt(
    *,
    deps: AppDeps,
    binding: ApprovalBinding,
    effect_execution_id: str,
    executable_inputs: Mapping[str, Any],
    capability_contract_json: str,
    outputs: Mapping[str, Any],
    claimed_outputs_hash: str,
    receipt_id: str | None,
) -> VerifiedEffectReceipt:
    """Return the independently recomputed hash for valid durable evidence."""

    try:
        spec = capability_spec_from_contract_json(capability_contract_json)
    except ApprovalRegistryError as exc:
        raise ApprovalReceiptError(
            str(exc),
            code="effect_start_authority_invalid",
            mismatches=exc.mismatches,
        ) from exc
    output_errors = validate_outputs(spec, outputs)
    if output_errors:
        raise ApprovalReceiptError(
            "; ".join(output_errors),
            code="effect_output_invalid",
            mismatches=("outputs",),
        )
    computed_hash = _hash_payload(outputs)
    if claimed_outputs_hash != computed_hash:
        raise ApprovalReceiptError(
            "claimed output hash does not match the canonical receipt payload",
            code="effect_output_hash_mismatch",
            mismatches=("outputs_hash",),
        )
    if _hash_payload(executable_inputs) != binding.input_hash:
        raise ApprovalReceiptError(
            "immutable effect-start inputs do not match the approved binding",
            code="effect_start_authority_invalid",
            mismatches=("input_hash",),
        )
    if spec.name == "promote_variant_lab":
        return _verify_lab_promotion_receipt(
            deps=deps,
            binding=binding,
            effect_execution_id=effect_execution_id,
            outputs=outputs,
            computed_hash=computed_hash,
            receipt_id=receipt_id,
        )
    if spec.name != "request_synthetic_validation":
        raise ApprovalReceiptError(
            "this governed capability has no executable receipt-provenance verifier",
            code="effect_receipt_unverifiable",
            mismatches=("receipt_provenance",),
        )
    job_id = outputs.get("validation_job_id")
    if type(job_id) is not str or not job_id or job_id != job_id.strip():
        raise ApprovalReceiptError(
            "synthetic validation receipt requires a canonical validation_job_id",
            code="effect_receipt_invalid",
            mismatches=("validation_job_id",),
        )
    job = deps.validation_jobs.get_job(job_id=job_id, client_id=binding.tenant_id)
    if job is None:
        raise ApprovalReceiptError(
            "synthetic validation receipt has no tenant-scoped durable provider job",
            code="effect_receipt_unverifiable",
            mismatches=("validation_job_id",),
        )
    inputs = dict(executable_inputs)
    expected_job = {
        "entity_type": "experiment_run",
        "entity_id": inputs.get("experiment_id"),
        "provider": inputs.get("provider"),
        "mode": inputs.get("mode"),
        "requested_model": inputs.get("model"),
        "prompt_version": inputs.get("prompt_version"),
    }
    job_mismatches = tuple(
        field for field, expected in expected_job.items() if job.get(field) != expected
    )
    effect_identity = {
        "agent_action_id": binding.action_id,
        "approval_id": binding.approval_id,
        "effect_idempotency_key": binding.effect_idempotency_key,
        "approval_effect_execution_id": effect_execution_id,
    }
    job_mismatches += tuple(
        field
        for field, expected in effect_identity.items()
        if job.get(field) != expected
    )
    if job_mismatches:
        raise ApprovalReceiptError(
            "durable provider job does not match the approved executable payload",
            code="effect_receipt_provenance_mismatch",
            mismatches=job_mismatches,
        )
    if _requires_completed_result(inputs):
        _verify_completed_validation_result(deps=deps, job=job)
    expected_receipt_id = f"validation-job:{job_id}"
    if receipt_id is not None and receipt_id != expected_receipt_id:
        raise ApprovalReceiptError(
            "receipt identity does not match the durable provider job",
            code="effect_receipt_provenance_mismatch",
            mismatches=("receipt_id",),
        )
    return VerifiedEffectReceipt(
        receipt_id=expected_receipt_id,
        outputs_hash=computed_hash,
    )


def _verify_lab_promotion_receipt(
    *,
    deps: AppDeps,
    binding: ApprovalBinding,
    effect_execution_id: str,
    outputs: Mapping[str, Any],
    computed_hash: str,
    receipt_id: str | None,
) -> VerifiedEffectReceipt:
    durable = deps.governed_effect_receipts.get_receipt_for_effect_execution(
        approval_effect_execution_id=effect_execution_id,
        tenant_id=binding.tenant_id,
    )
    if durable is None:
        raise ApprovalReceiptError(
            "lab promotion has no tenant-scoped durable effect receipt",
            code="effect_receipt_unverifiable",
            mismatches=("approval_effect_execution_id",),
        )
    expected_identity = {
        "tenant_id": binding.tenant_id,
        "workflow_id": binding.workflow_id,
        "action_id": binding.action_id,
        "approval_id": binding.approval_id,
        "effect_idempotency_key": binding.effect_idempotency_key,
        "approval_effect_execution_id": effect_execution_id,
        "capability_name": "promote_variant_lab",
        "scope_status": "validated",
        "source_metric_id": outputs.get("source_metric_id"),
    }
    mismatches = tuple(
        field
        for field, expected in expected_identity.items()
        if durable.get(field) != expected
    )
    if durable.get("outputs") != dict(outputs):
        mismatches += ("outputs",)
    if durable.get("outputs_hash") != computed_hash:
        mismatches += ("outputs_hash",)
    analytics_event = deps.analytics_events.get_event(
        str(durable.get("analytics_event_id") or "")
    )
    decision_event = deps.decision_events.get_decision_event(
        event_id=str(durable.get("decision_event_id") or "")
    )
    if not _lab_analytics_event_matches(
        event=analytics_event, tenant_id=binding.tenant_id, outputs=outputs
    ):
        mismatches += ("analytics_event",)
    if not _lab_decision_event_matches(
        event=decision_event, tenant_id=binding.tenant_id, outputs=outputs
    ):
        mismatches += ("decision_event",)
    expected_receipt_id = f"lab-promotion:{effect_execution_id}"
    if durable.get("receipt_id") != expected_receipt_id:
        mismatches += ("receipt_id",)
    if receipt_id is not None and receipt_id != expected_receipt_id:
        mismatches += ("receipt_id",)
    if mismatches:
        raise ApprovalReceiptError(
            "durable lab-promotion evidence does not match the exact effect start",
            code="effect_receipt_provenance_mismatch",
            mismatches=tuple(dict.fromkeys(mismatches)),
        )
    return VerifiedEffectReceipt(
        receipt_id=expected_receipt_id,
        outputs_hash=computed_hash,
    )


def _lab_analytics_event_matches(
    *, event: Mapping[str, Any] | None, tenant_id: str, outputs: Mapping[str, Any]
) -> bool:
    if event is None:
        return False
    metadata = event.get("metadata")
    return (
        event.get("id") == outputs.get("analytics_event_id")
        and event.get("client_id") == tenant_id
        and event.get("experiment_id") == outputs.get("experiment_id")
        and event.get("variant_id") == outputs.get("variant_id")
        and event.get("event_type") == "variant_promoted_lab"
        and event.get("source") == "agent_runtime"
        and type(metadata) is dict
        and metadata.get("reason") == outputs.get("reason")
        and metadata.get("metric_id") == outputs.get("source_metric_id")
        and metadata.get("posterior") == outputs.get("posterior")
        and metadata.get("decision_action") == outputs.get("decision_action")
        and metadata.get("decision_tier") == outputs.get("decision_tier")
        and metadata.get("policy_version") == outputs.get("decision_policy_version")
    )


def _lab_decision_event_matches(
    *, event: Mapping[str, Any] | None, tenant_id: str, outputs: Mapping[str, Any]
) -> bool:
    posterior = outputs.get("posterior")
    try:
        confidence = float(posterior) if posterior is not None else 0.0
    except (TypeError, ValueError):
        return False
    confidence = max(0.0, min(1.0, confidence))
    return bool(
        event is not None
        and event.get("id") == outputs.get("decision_event_id")
        and event.get("client_id") == tenant_id
        and event.get("policy_action") == "promote_variant_lab"
        and event.get("selected_reason") == outputs.get("reason")
        and event.get("expected_gain") == confidence
        and event.get("uncertainty") == 1.0 - confidence
    )


def _requires_completed_result(inputs: Mapping[str, Any]) -> bool:
    mode = inputs.get("mode")
    normalized_mode = mode.strip().lower() if type(mode) is str else None
    return inputs.get("auto_run") is True and normalized_mode in {
        "in_app",
        "in_app_byok",
    }


def _verify_completed_validation_result(
    *, deps: AppDeps, job: Mapping[str, Any]
) -> None:
    if job.get("status") != "completed":
        raise ApprovalReceiptError(
            "auto-run validation receipt requires a completed durable provider job",
            code="effect_receipt_outcome_incomplete",
            mismatches=("validation_job_status",),
        )
    result = deps.validation_results.get_latest_for_job(job_id=job["id"])
    if result is None:
        raise ApprovalReceiptError(
            "auto-run validation receipt requires a durable validation result",
            code="effect_receipt_outcome_incomplete",
            mismatches=("validation_result",),
        )
    expected_result = {
        "job_id": job.get("id"),
        "provider": job.get("provider"),
        "model": job.get("requested_model"),
    }
    result_mismatches = tuple(
        field
        for field, expected in expected_result.items()
        if result.get(field) != expected
    )
    if result_mismatches:
        raise ApprovalReceiptError(
            "durable validation result does not match its completed provider job",
            code="effect_receipt_provenance_mismatch",
            mismatches=tuple(
                f"validation_result_{field}" for field in result_mismatches
            ),
        )


def _hash_payload(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "ApprovalReceiptError",
    "VerifiedEffectReceipt",
    "verify_effect_receipt",
]
