"""Admission and pre-effect consumption of exact durable approvals."""

from __future__ import annotations

import uuid
import hashlib
import json
from dataclasses import dataclass, fields, replace
from datetime import datetime, timezone
from typing import Any, Mapping

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_ledger import (
    ApprovalLedgerError,
    build_action_approval_binding,
    get_authoritative_approval,
)
from application.services.agent_runtime.registry import CapabilitySpec
from domain.workflow.approval import (
    ApprovalBinding,
    ApprovalStatus,
    transition_approval,
)
from domain.workflow.approval_execution import approval_execution_source_digest
from domain.workflow.approval_serialization import (
    approval_envelope_digest,
    approval_envelope_from_payload,
    approval_envelope_payload,
)


GOVERNED_EFFECT_CLASSES = frozenset({"external_side_effect", "write_high_risk"})


class ApprovalAuthorizationError(ValueError):
    def __init__(self, message: str, *, code: str, mismatches: tuple[str, ...] = ()):
        super().__init__(message)
        self.code = code
        self.mismatches = mismatches


@dataclass(frozen=True)
class ExactApprovalAuthorization:
    approval_id: str
    envelope_digest: str
    effect_idempotency_key: str
    authorization_source_digest: str
    binding: ApprovalBinding
    execution_id: str | None = None


def requires_exact_approval(*, run: Mapping[str, Any], spec: CapabilitySpec) -> bool:
    profile = str(run.get("policy_profile_id") or "").strip().lower()
    return (
        spec.effect_class in GOVERNED_EFFECT_CLASSES
        or profile == "human_approval_required"
    )


def validate_exact_action_approval(
    *,
    deps: AppDeps,
    run: dict[str, Any],
    action: dict[str, Any],
    spec: CapabilitySpec,
    now: datetime | None = None,
) -> ExactApprovalAuthorization | None:
    """Recompute every binding dimension from current authoritative state."""

    if not requires_exact_approval(run=run, spec=spec):
        return None
    approval_id = _require_identifier("approval_id", action.get("approval_id"))
    pinned_digest = _require_digest(
        "approval_envelope_digest", action.get("approval_envelope_digest")
    )
    tenant_id = _require_identifier("tenant_id", run.get("client_id"))
    workflow_id = _require_identifier("workflow_id", run.get("id"))
    try:
        row = get_authoritative_approval(
            deps=deps,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            approval_id=approval_id,
        )
    except ApprovalLedgerError as exc:
        raise ApprovalAuthorizationError(
            str(exc), code="approval_history_invalid"
        ) from exc
    if row is None:
        raise ApprovalAuthorizationError(
            "governed effect requires an authoritative approval record",
            code="approval_not_found",
        )
    if row.get("action_id") != action.get("id"):
        raise ApprovalAuthorizationError(
            "approval belongs to a different governed action",
            code="approval_action_mismatch",
            mismatches=("action_id",),
        )
    if row.get("envelope_digest") != pinned_digest:
        raise ApprovalAuthorizationError(
            "action approval digest does not match the authoritative ledger",
            code="approval_digest_mismatch",
            mismatches=("envelope_digest",),
        )
    try:
        envelope = approval_envelope_from_payload(dict(row["envelope"]))
    except Exception as exc:
        raise ApprovalAuthorizationError(
            "approval envelope failed canonical validation",
            code="approval_history_invalid",
        ) from exc
    if envelope.status is not ApprovalStatus.APPROVED:
        raise ApprovalAuthorizationError(
            f"approval is {envelope.status.value}, not approved",
            code="approval_not_active",
            mismatches=("status",),
        )
    checked_at = _normalize_utc(now or datetime.now(timezone.utc))
    if checked_at >= envelope.binding.expires_at:
        raise ApprovalAuthorizationError(
            "approval expired before effect execution",
            code="approval_expired",
            mismatches=("expires_at",),
        )
    try:
        expected = build_action_approval_binding(
            run=run,
            action=action,
            approval_id=approval_id,
            requested_at=envelope.binding.requested_at,
            expires_at=envelope.binding.expires_at,
            native_target=envelope.binding.native_target,
        )
    except ApprovalLedgerError as exc:
        raise ApprovalAuthorizationError(
            str(exc),
            code="approval_binding_invalid",
            mismatches=("binding_source",),
        ) from exc
    mismatches = _binding_mismatches(expected, envelope.binding)
    if mismatches:
        raise ApprovalAuthorizationError(
            "current effect no longer matches its exact approval: "
            + ", ".join(mismatches),
            code="approval_binding_mismatch",
            mismatches=mismatches,
        )
    return ExactApprovalAuthorization(
        approval_id=approval_id,
        envelope_digest=approval_envelope_digest(envelope),
        effect_idempotency_key=envelope.binding.effect_idempotency_key,
        authorization_source_digest=approval_execution_source_digest(
            run=run, action=action
        ),
        binding=envelope.binding,
    )


def commit_pre_effect_authorization(
    *,
    deps: AppDeps,
    run: dict[str, Any],
    action: dict[str, Any],
    spec: CapabilitySpec,
    now: datetime | None = None,
) -> ExactApprovalAuthorization | None:
    """Commit the exact approval use at the effect linearization point."""

    checked_at = _normalize_utc(now or datetime.now(timezone.utc))
    authorization = validate_exact_action_approval(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        now=checked_at,
    )
    if authorization is None:
        return None
    result = deps.approval_ledger.commit_effect_authorization(
        execution_id=str(uuid.uuid4()),
        tenant_id=authorization.binding.tenant_id,
        workflow_id=authorization.binding.workflow_id,
        action_id=authorization.binding.action_id,
        approval_id=authorization.approval_id,
        envelope_digest=authorization.envelope_digest,
        authorization_source_digest=authorization.authorization_source_digest,
        effect_idempotency_key=authorization.effect_idempotency_key,
        authorized_at=_format_datetime(checked_at),
        audit_event=_effect_event(
            run=run,
            action=action,
            authorization=authorization,
            event_type="approval_effect_started",
            status="started",
            note="Exact approval consumed at pre-effect commit",
        ),
    )
    outcome = str(result.get("outcome") or "")
    if outcome == "started":
        execution = dict(result.get("execution") or {})
        return replace(
            authorization,
            execution_id=_require_identifier(
                "execution_id", execution.get("execution_id")
            ),
        )
    if outcome in {"reconcile", "completed"}:
        raise ApprovalAuthorizationError(
            "effect identity already started; reconcile its durable receipt instead of executing again",
            code="effect_reconciliation_required",
        )
    raise ApprovalAuthorizationError(
        str(result.get("reason") or "pre-effect authorization failed"),
        code="effect_identity_conflict"
        if outcome == "identity_conflict"
        else "approval_changed_before_effect",
    )


def complete_authorized_effect(
    *,
    deps: AppDeps,
    run: dict[str, Any],
    action: dict[str, Any],
    authorization: ExactApprovalAuthorization | None,
    outputs: dict[str, Any],
    outputs_hash: str,
    now: datetime | None = None,
    receipt_id: str | None = None,
) -> dict[str, Any] | None:
    """Persist the receipt and fulfillment atomically for a governed effect."""

    if authorization is None:
        return None
    execution_id = _require_identifier("execution_id", authorization.execution_id)
    completed_at = _normalize_utc(now or datetime.now(timezone.utc))
    row = get_authoritative_approval(
        deps=deps,
        tenant_id=authorization.binding.tenant_id,
        workflow_id=authorization.binding.workflow_id,
        approval_id=authorization.approval_id,
    )
    if row is None:
        raise ApprovalAuthorizationError(
            "approval disappeared before effect receipt commit",
            code="approval_not_found",
        )
    envelope = approval_envelope_from_payload(dict(row["envelope"]))
    if (
        envelope.status is not ApprovalStatus.APPROVED
        or approval_envelope_digest(envelope) != authorization.envelope_digest
    ):
        raise ApprovalAuthorizationError(
            "approval changed before effect receipt commit",
            code="approval_changed_after_effect",
        )
    normalized_receipt = receipt_id or f"approval-effect-receipt:{uuid.uuid4()}"
    fulfilled = transition_approval(
        envelope,
        ApprovalStatus.FULFILLED,
        occurred_at=completed_at,
        fulfillment_receipt_id=normalized_receipt,
    )
    sequence = int(row["sequence"]) + 1
    mutation = {
        "approval_id": authorization.approval_id,
        "action_id": authorization.binding.action_id,
        "sequence": sequence,
        "expected_sequence": int(row["sequence"]),
        "event_type": "approval_fulfilled",
        "status": "fulfilled",
        "envelope": approval_envelope_payload(fulfilled),
        "envelope_digest": approval_envelope_digest(fulfilled),
        "occurred_at": _format_datetime(completed_at),
    }
    result_core = {
        "approval_id": authorization.approval_id,
        "effect_idempotency_key": authorization.effect_idempotency_key,
        "receipt_id": normalized_receipt,
        "outputs_hash": outputs_hash,
    }
    result = {**result_core, "result_hash": _hash_payload(result_core)}
    response = deps.approval_ledger.commit_effect_completion(
        execution_id=execution_id,
        tenant_id=authorization.binding.tenant_id,
        workflow_id=authorization.binding.workflow_id,
        action_id=authorization.binding.action_id,
        approval_id=authorization.approval_id,
        expected_envelope_digest=authorization.envelope_digest,
        effect_idempotency_key=authorization.effect_idempotency_key,
        receipt_id=normalized_receipt,
        outputs=outputs,
        outputs_hash=outputs_hash,
        completed_at=_format_datetime(completed_at),
        command_id=str(uuid.uuid4()),
        idempotency_key=(f"effect-fulfillment:{authorization.effect_idempotency_key}"),
        request_hash=_hash_payload(
            {
                "contract": "workflow.effect-fulfillment",
                "version": "1.0",
                **result_core,
            }
        ),
        result=result,
        mutation=mutation,
        audit_events=[
            _effect_event(
                run=run,
                action=action,
                authorization=authorization,
                event_type="approval_effect_succeeded",
                status="succeeded",
                note="Governed effect receipt committed",
                extra_anchors={"receipt_id": normalized_receipt},
            ),
            _effect_event(
                run=run,
                action=action,
                authorization=authorization,
                event_type="approval_fulfilled",
                status="fulfilled",
                note="Exact approval fulfilled by durable effect receipt",
                extra_anchors={"receipt_id": normalized_receipt},
            ),
            _effect_event(
                run=run,
                action=action,
                authorization=authorization,
                event_type="action_executed",
                status="executed",
                note="Governed action executed with exact approval receipt",
                extra_anchors={"receipt_id": normalized_receipt},
            ),
        ],
    )
    outcome = str(response.get("outcome") or "")
    if outcome not in {"committed", "replayed"}:
        raise ApprovalAuthorizationError(
            str(response.get("reason") or "effect receipt commit failed"),
            code="effect_receipt_commit_failed",
        )
    return dict(response.get("execution") or {})


def mark_authorized_effect_uncertain(
    *,
    deps: AppDeps,
    run: dict[str, Any],
    action: dict[str, Any],
    authorization: ExactApprovalAuthorization | None,
    error_code: str,
    now: datetime | None = None,
) -> None:
    if authorization is None or authorization.execution_id is None:
        return
    occurred_at = _normalize_utc(now or datetime.now(timezone.utc))
    deps.approval_ledger.mark_effect_execution_uncertain(
        execution_id=authorization.execution_id,
        tenant_id=authorization.binding.tenant_id,
        workflow_id=authorization.binding.workflow_id,
        action_id=authorization.binding.action_id,
        error_code=error_code,
        occurred_at=_format_datetime(occurred_at),
        audit_event=_effect_event(
            run=run,
            action=action,
            authorization=authorization,
            event_type="approval_effect_uncertain",
            status="uncertain",
            note="Effect outcome requires receipt reconciliation",
            extra_anchors={"error_code": error_code},
        ),
    )


def reconcile_authorized_effect(
    *,
    deps: AppDeps,
    run: dict[str, Any],
    action: dict[str, Any],
    spec: CapabilitySpec,
    outputs: dict[str, Any],
    outputs_hash: str,
    receipt_id: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Commit durable evidence for a previously started or uncertain effect.

    Reconciliation reconstructs authorization from the ledger, so it remains
    safe after process loss and never invokes the capability again.
    """

    tenant_id = _require_identifier("tenant_id", run.get("client_id"))
    workflow_id = _require_identifier("workflow_id", run.get("id"))
    effect_key = _require_identifier("effect_idempotency_key", action.get("dedupe_key"))
    execution = deps.approval_ledger.get_effect_execution(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        effect_idempotency_key=effect_key,
    )
    if execution is None:
        raise ApprovalAuthorizationError(
            "no durable effect start exists for reconciliation",
            code="effect_execution_not_found",
        )
    if execution.get("action_id") != action.get("id"):
        raise ApprovalAuthorizationError(
            "durable effect belongs to a different action",
            code="effect_identity_conflict",
            mismatches=("action_id",),
        )
    if execution.get("status") == "succeeded":
        if (
            execution.get("receipt_id") == receipt_id
            and execution.get("outputs_hash") == outputs_hash
        ):
            return dict(execution)
        raise ApprovalAuthorizationError(
            "completed effect was redelivered with conflicting receipt evidence",
            code="effect_identity_conflict",
        )
    if execution.get("status") not in {"started", "uncertain"}:
        raise ApprovalAuthorizationError(
            "effect is not awaiting reconciliation",
            code="effect_state_conflict",
        )
    authorization = validate_exact_action_approval(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        now=now,
    )
    if authorization is None:
        raise ApprovalAuthorizationError(
            "effect is not governed by exact approval",
            code="approval_not_required",
        )
    expected = {
        "approval_id": authorization.approval_id,
        "approval_envelope_digest": authorization.envelope_digest,
        "authorization_source_digest": authorization.authorization_source_digest,
        "effect_idempotency_key": authorization.effect_idempotency_key,
    }
    mismatches = tuple(
        field for field, value in expected.items() if execution.get(field) != value
    )
    if mismatches:
        raise ApprovalAuthorizationError(
            "durable effect start no longer matches its exact authorization",
            code="effect_identity_conflict",
            mismatches=mismatches,
        )
    reconciled = complete_authorized_effect(
        deps=deps,
        run=run,
        action=action,
        authorization=replace(
            authorization,
            execution_id=_require_identifier(
                "execution_id", execution.get("execution_id")
            ),
        ),
        outputs=outputs,
        outputs_hash=outputs_hash,
        receipt_id=receipt_id,
        now=now,
    )
    if reconciled is None:
        raise ApprovalAuthorizationError(
            "effect reconciliation did not produce a durable outcome",
            code="effect_receipt_commit_failed",
        )
    return reconciled


def denial_event(
    *,
    run: Mapping[str, Any],
    action: Mapping[str, Any],
    error: ApprovalAuthorizationError,
    phase: str,
) -> dict[str, Any]:
    return {
        "agent_run_id": str(run.get("id") or ""),
        "action_id": str(action.get("id") or ""),
        "sequence": int(action.get("sequence") or 0),
        "event_type": "approval_authorization_denied",
        "status": "denied",
        "capability_name": action.get("capability_name"),
        "capability_version": action.get("capability_version"),
        "principal_type": run.get("principal_type"),
        "principal_id": run.get("principal_id"),
        "tool_id": action.get("tool_id"),
        "skill_id": action.get("skill_id"),
        "effect_class": action.get("effect_class"),
        "trace_id": run.get("trace_id"),
        "note": str(error),
        "is_policy_event": True,
        "anchors": {
            "approval_id": action.get("approval_id"),
            "approval_envelope_digest": action.get("approval_envelope_digest"),
            "authorization_phase": phase,
            "denial_code": error.code,
            "mismatch_fields": list(error.mismatches),
        },
    }


def _effect_event(
    *,
    run: Mapping[str, Any],
    action: Mapping[str, Any],
    authorization: ExactApprovalAuthorization,
    event_type: str,
    status: str,
    note: str,
    extra_anchors: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "sequence": int(action.get("sequence") or 0),
        "event_type": event_type,
        "status": status,
        "capability_name": action.get("capability_name"),
        "capability_version": action.get("capability_version"),
        "principal_type": run.get("principal_type"),
        "principal_id": run.get("principal_id"),
        "tool_id": action.get("tool_id"),
        "skill_id": action.get("skill_id"),
        "effect_class": action.get("effect_class"),
        "trace_id": run.get("trace_id"),
        "note": note,
        "is_policy_event": True,
        "anchors": {
            "approval_id": authorization.approval_id,
            "approval_envelope_digest": authorization.envelope_digest,
            "authorization_source_digest": authorization.authorization_source_digest,
            "effect_idempotency_key": authorization.effect_idempotency_key,
            **dict(extra_anchors or {}),
        },
    }


def _binding_mismatches(
    expected: ApprovalBinding, actual: ApprovalBinding
) -> tuple[str, ...]:
    return tuple(
        field.name
        for field in fields(ApprovalBinding)
        if getattr(expected, field.name) != getattr(actual, field.name)
    )


def _require_identifier(field_name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ApprovalAuthorizationError(
            f"governed effect requires a canonical {field_name}",
            code=f"missing_{field_name}",
            mismatches=(field_name,),
        )
    return value


def _require_digest(field_name: str, value: object) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise ApprovalAuthorizationError(
            f"governed effect requires a canonical {field_name}",
            code=f"missing_{field_name}",
            mismatches=(field_name,),
        )
    return value


def _normalize_utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ApprovalAuthorizationError(
            "authorization time must be an aware built-in datetime",
            code="invalid_authorization_time",
        )
    if type(value.tzinfo) is not timezone:
        raise ApprovalAuthorizationError(
            "authorization time must use a built-in fixed-offset timezone",
            code="invalid_authorization_time",
        )
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


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
    "ApprovalAuthorizationError",
    "ExactApprovalAuthorization",
    "GOVERNED_EFFECT_CLASSES",
    "complete_authorized_effect",
    "commit_pre_effect_authorization",
    "denial_event",
    "requires_exact_approval",
    "mark_authorized_effect_uncertain",
    "reconcile_authorized_effect",
    "validate_exact_action_approval",
]
