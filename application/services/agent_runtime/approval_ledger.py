from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from application.ports.deps import AppDeps
from application.services.agent_runtime.agent_first import (
    capability_to_tool_id,
    tool_effect_class,
)
from application.services.agent_runtime.policy import PolicyEnforcer, PolicyError
from application.services.agent_runtime.approval_registry import (
    ApprovalRegistryError,
    prepare_action_for_exact_approval,
)
from application.services.agent_runtime.registry import (
    get_capability_spec,
)
from domain.workflow.approval import (
    APPROVAL_ENVELOPE_SCHEMA_VERSION,
    ApprovalAuthority,
    ApprovalBinding,
    ApprovalContractError,
    ApprovalEnvelope,
    ApprovalStatus,
    EffectClass,
    PrincipalType,
    create_approval_request,
    transition_approval,
)
from domain.workflow.approval_serialization import (
    approval_envelope_digest,
    approval_envelope_from_payload,
    approval_envelope_payload,
)
from domain.workflow.approval_execution import approval_execution_source_digest


DEFAULT_APPROVAL_TTL_SECONDS = 900
MAX_APPROVAL_TTL_SECONDS = 86_400
SUPPORTED_APPROVAL_COMMANDS = frozenset(
    {"request", "approve", "reject", "revoke", "expire", "supersede"}
)
DECIDABLE_ACTION_STATUSES = frozenset({"proposed", "approved"})


class ApprovalLedgerError(ValueError):
    def __init__(self, message: str, *, code: str, status_code: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


def issue_action_approval_command(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    command_type: str,
    approving_authority: ApprovalAuthority,
    idempotency_key: str,
    occurred_at: datetime | None = None,
    approval_id: str | None = None,
    expected_sequence: int | None = None,
    ttl_seconds: int | None = None,
    revocation_reference: str | None = None,
    supersession_reference: str | None = None,
    audit_context: str = "action_decision",
    command_context_digest: str | None = None,
) -> Dict[str, Any]:
    """Apply one attributable, retry-safe approval command.

    The application owns domain transitions; the adapter owns the single
    transaction that persists snapshots, receipt, audit event and compatibility
    projection.
    """

    operation = _normalize_operation(command_type)
    tenant_id, workflow_id, action_id = _require_scope(run=run, action=action)
    run, action = _reload_authoritative_scope(
        deps=deps,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        action_id=action_id,
    )
    approving_authority.validate()
    normalized_key = _require_canonical_identifier("idempotency_key", idempotency_key)
    normalized_approval_id = _optional_identifier("approval_id", approval_id)
    normalized_revocation = _optional_identifier(
        "revocation_reference", revocation_reference
    )
    normalized_supersession = _optional_identifier(
        "supersession_reference", supersession_reference
    )
    if command_context_digest is not None and not _is_digest(command_context_digest):
        raise ApprovalLedgerError(
            "command_context_digest must be a lowercase SHA-256 digest",
            code="invalid_command_context_digest",
            status_code=400,
        )
    if expected_sequence is not None and (
        type(expected_sequence) is not int or expected_sequence < 1
    ):
        raise ApprovalLedgerError(
            "expected_sequence must be a positive exact integer",
            code="invalid_expected_sequence",
            status_code=400,
        )

    request_hash = _hash_payload(
        {
            "contract": "workflow.approval-command",
            "version": "1.0",
            "tenant_id": tenant_id,
            "workflow_id": workflow_id,
            "action_id": action_id,
            "command_type": operation,
            "approval_id": normalized_approval_id,
            "expected_sequence": expected_sequence,
            "ttl_seconds": ttl_seconds,
            "revocation_reference": normalized_revocation,
            "supersession_reference": normalized_supersession,
            "audit_context": audit_context,
            "command_context_digest": command_context_digest,
            "authority": _authority_payload(approving_authority),
        }
    )
    replay = deps.approval_ledger.get_command_by_idempotency_key(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        idempotency_key=normalized_key,
    )
    if replay:
        if replay["request_hash"] != request_hash:
            raise ApprovalLedgerError(
                "idempotency key was already used with a different approval command",
                code="idempotency_key_reused",
            )
        return _command_response(deps=deps, command=replay, replayed=True)

    now = _normalize_utc(occurred_at or datetime.now(timezone.utc))
    current = _load_current_approval(
        deps=deps,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        action_id=action_id,
        approval_id=normalized_approval_id,
    )
    if current is None and operation == "approve":
        _validate_action_policy(run=run, action=action)
    approval_normalization: Dict[str, Any] | None = None
    if current is None:
        spec = get_capability_spec(str(action.get("capability_name") or ""))
        if spec is None:
            raise ApprovalLedgerError(
                "governed capability is absent from the executable registry",
                code="approval_registry_mismatch",
                status_code=400,
            )
        source_before_normalization = approval_execution_source_digest(
            run=run, action=action
        )
        try:
            prepared_action, _ = prepare_action_for_exact_approval(
                deps=deps,
                run=run,
                action=action,
                spec=spec,
            )
        except ApprovalRegistryError as exc:
            raise ApprovalLedgerError(
                str(exc), code="approval_registry_mismatch", status_code=409
            ) from exc
        approval_normalization = {
            "expected_source_digest": source_before_normalization,
            "normalized_inputs": prepared_action["inputs"],
            "normalized_inputs_hash": prepared_action["inputs_hash"],
            "normalized_source_digest": approval_execution_source_digest(
                run=run, action=prepared_action
            ),
        }
        action = prepared_action
    expected_action_status = _expected_action_status(
        action=action,
        current=current,
        operation=operation,
    )
    if expected_sequence is not None and (
        current is None or int(current["sequence"]) != expected_sequence
    ):
        raise ApprovalLedgerError(
            "approval version changed before command evaluation",
            code="approval_version_conflict",
        )

    mutations: list[Dict[str, Any]] = []
    if current is None:
        if operation not in {"request", "approve", "reject"}:
            raise ApprovalLedgerError(
                f"{operation} requires an existing approval",
                code="approval_not_found",
                status_code=404,
            )
        requested = _new_request(
            run=run,
            action=action,
            now=now,
            approval_id=normalized_approval_id or str(uuid.uuid4()),
            ttl_seconds=ttl_seconds,
        )
        mutations.append(
            _mutation(
                requested,
                sequence=1,
                expected_sequence=None,
                require_no_existing_action_approval=operation in {"approve", "reject"},
            )
        )
        envelope = requested
        sequence = 1
    else:
        envelope = _parse_stored_envelope(current)
        sequence = int(current["sequence"])

    if operation == "request":
        if current is not None:
            raise ApprovalLedgerError(
                "an approval already exists for this governed action",
                code="live_approval_exists",
            )
        final_envelope = envelope
    else:
        final_envelope = _transition_for_command(
            deps=deps,
            run=run,
            action=action,
            envelope=envelope,
            operation=operation,
            occurred_at=now,
            approving_authority=approving_authority,
            revocation_reference=normalized_revocation,
            supersession_reference=normalized_supersession,
        )
        sequence += 1
        mutations.append(
            _mutation(
                final_envelope,
                sequence=sequence,
                expected_sequence=sequence - 1,
            )
        )

    projection = _approval_projection(final_envelope, sequence=sequence)
    result_core = {
        "approval": projection,
        "decision": operation,
    }
    result = {**result_core, "result_hash": _hash_payload(result_core)}
    command_id = str(uuid.uuid4())
    stored = deps.approval_ledger.commit_approval_command(
        command_id=command_id,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        action_id=action_id,
        approval_id=final_envelope.binding.approval_id,
        command_type=operation,
        principal_type=approving_authority.principal_type.value,
        principal_id=approving_authority.principal_id,
        authority_source=approving_authority.authority_source,
        authority_version=approving_authority.authority_version,
        idempotency_key=normalized_key,
        request_hash=request_hash,
        received_at=_format_datetime(now),
        completed_at=_format_datetime(now),
        mutations=mutations,
        result=result,
        expected_action_status=expected_action_status,
        action_status=_legacy_action_projection(final_envelope.status),
        audit_events=_audit_events(
            run=run,
            action=action,
            command_id=command_id,
            envelope=final_envelope,
            envelope_digest=projection["envelope_digest"],
            operation=operation,
            audit_context=audit_context,
        ),
        approval_normalization=approval_normalization,
    )
    outcome = str(stored.get("outcome") or "")
    if outcome == "idempotency_conflict":
        raise ApprovalLedgerError(
            "idempotency key was already used with a different approval command",
            code="idempotency_key_reused",
        )
    if outcome == "concurrency_conflict":
        raise ApprovalLedgerError(
            "another approval decision won the concurrency race",
            code="approval_version_conflict",
        )
    if outcome == "action_state_conflict":
        raise ApprovalLedgerError(
            "governed action lifecycle state changed before approval commit",
            code="action_state_conflict",
        )
    if outcome == "validation_error":
        raise ApprovalLedgerError(
            str(stored.get("reason") or "approval integrity validation failed"),
            code=str(stored.get("code") or "approval_integrity_error"),
            status_code=int(stored.get("status_code") or 409),
        )
    command = stored.get("command")
    if not isinstance(command, dict):
        raise ApprovalLedgerError(
            "approval command did not produce a durable receipt",
            code="approval_commit_failed",
            status_code=500,
        )
    return _command_response(
        deps=deps,
        command=command,
        replayed=outcome == "replayed",
    )


def list_action_approvals(
    *, deps: AppDeps, tenant_id: str, workflow_id: str, action_id: str
) -> list[Dict[str, Any]]:
    approvals = deps.approval_ledger.list_approvals_for_action(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        action_id=action_id,
        limit=100,
    )
    for approval in approvals:
        _validate_record_history(deps=deps, row=approval)
        approval["events"] = deps.approval_ledger.list_approval_events(
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            approval_id=approval["approval_id"],
            limit=200,
        )
    return approvals


def get_authoritative_approval(
    *, deps: AppDeps, tenant_id: str, workflow_id: str, approval_id: str
) -> Dict[str, Any] | None:
    """Resolve and verify one ledger projection against immutable history."""

    row = deps.approval_ledger.get_approval(
        approval_id=approval_id,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
    )
    if row:
        _validate_record_history(deps=deps, row=row)
    return row


def _load_current_approval(
    *,
    deps: AppDeps,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
    approval_id: str | None,
) -> Dict[str, Any] | None:
    if approval_id:
        scoped = deps.approval_ledger.get_approval(
            approval_id=approval_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id,
        )
        if scoped and scoped["action_id"] != action_id:
            raise ApprovalLedgerError(
                "approval is not bound to the governed action",
                code="approval_scope_mismatch",
                status_code=404,
            )
        if scoped:
            _validate_record_history(deps=deps, row=scoped)
        return scoped
    current = deps.approval_ledger.get_current_approval_for_action(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        action_id=action_id,
    )
    if current:
        _validate_record_history(deps=deps, row=current)
    return current


def _expected_action_status(
    *,
    action: Dict[str, Any],
    current: Dict[str, Any] | None,
    operation: str,
) -> str:
    status = str(action.get("status") or "").strip().lower()
    allowed = DECIDABLE_ACTION_STATUSES
    if current is None and operation == "request":
        allowed = frozenset({"proposed"})
    elif current is not None:
        approval_status = str(current.get("status") or "")
        allowed = (
            frozenset({"proposed"})
            if approval_status == ApprovalStatus.REQUESTED.value
            else (
                frozenset({"approved", "executing"})
                if operation in {"reject", "revoke", "expire", "supersede"}
                else frozenset({"approved"})
            )
            if approval_status == ApprovalStatus.APPROVED.value
            else frozenset()
        )
    if status not in allowed:
        raise ApprovalLedgerError(
            f"governed action cannot accept {operation} in its current lifecycle state",
            code="action_not_decidable",
        )
    return status


def _new_request(
    *,
    run: Dict[str, Any],
    action: Dict[str, Any],
    now: datetime,
    approval_id: str,
    ttl_seconds: int | None,
) -> ApprovalEnvelope:
    ttl = _approval_ttl(run=run, requested=ttl_seconds)
    binding = build_action_approval_binding(
        run=run,
        action=action,
        approval_id=approval_id,
        requested_at=now,
        expires_at=now + timedelta(seconds=ttl),
    )
    return create_approval_request(binding)


def build_action_approval_binding(
    *,
    run: Dict[str, Any],
    action: Dict[str, Any],
    approval_id: str,
    requested_at: datetime,
    expires_at: datetime,
    native_target: Any = None,
) -> ApprovalBinding:
    """Rebuild the exact approval scope from current authoritative runtime state."""

    capability_id = _require_canonical_identifier(
        "capability_id", str(action.get("capability_name") or "")
    )
    tool_id = _require_canonical_identifier(
        "tool_id",
        str(action.get("tool_id") or capability_to_tool_id(capability_id) or ""),
    )
    effect_value = str(
        action.get("effect_class") or tool_effect_class(tool_id) or "recommend"
    )
    try:
        effect_class = EffectClass(effect_value)
    except ValueError as exc:
        raise ApprovalLedgerError(
            f"unsupported effect class {effect_value!r}",
            code="invalid_effect_class",
            status_code=400,
        ) from exc
    principal_type = _principal_type(run.get("principal_type"))
    principal_id = str(run.get("principal_id") or "").strip()
    if not principal_id:
        principal_id = f"{principal_type.value}:{run['client_id']}:legacy-run"
    registry_version = str(
        action.get("registry_version")
        or run.get("registry_version")
        or "legacy-unpinned-registry-v1"
    ).strip()
    registry_fingerprint = str(
        action.get("registry_fingerprint") or run.get("registry_fingerprint") or ""
    ).strip()
    if not _is_digest(registry_fingerprint):
        registry_fingerprint = _hash_payload(
            {"registry_version": registry_version, "legacy_unpinned": True}
        )
    harness_id = str(run.get("harness_id") or "operator_supervised").strip()
    policy_profile_id = str(
        run.get("policy_profile_id") or "human_approval_required"
    ).strip()
    computed_input_hash = _hash_payload(action.get("inputs") or {})
    input_hash = str(action.get("inputs_hash") or "").strip()
    if _is_digest(input_hash) and input_hash != computed_input_hash:
        raise ApprovalLedgerError(
            "governed action input hash does not match its persisted inputs",
            code="action_input_hash_mismatch",
            status_code=500,
        )
    if not _is_digest(input_hash):
        input_hash = computed_input_hash
    payload_hash = _hash_payload(
        {
            "action_id": action["id"],
            "capability_id": capability_id,
            "capability_version": action.get("capability_version"),
            "tool_id": tool_id,
            "tool_version": action.get("tool_version"),
            "effect_class": effect_class.value,
            "inputs": action.get("inputs") or {},
        }
    )
    evidence_digest = _hash_payload(
        {
            "snapshot_version": action.get("snapshot_version"),
            "hypothesis_id": action.get("hypothesis_id"),
            "variant_id": action.get("variant_id"),
            "validation_job_id": action.get("validation_job_id"),
            "rationale": action.get("rationale"),
            "confidence": action.get("confidence"),
        }
    )
    authority_hash = _hash_payload(
        {
            "tenant_id": run["client_id"],
            "principal_type": principal_type.value,
            "principal_id": principal_id,
            "workflow_id": run["id"],
            "allowed_capabilities": sorted(
                str(item) for item in list(run.get("allowed_capabilities") or [])
            ),
            "budgets": run.get("budgets") or {},
            "registry_fingerprint": registry_fingerprint,
            "harness_id": harness_id,
            "policy_profile_id": policy_profile_id,
        }
    )
    return ApprovalBinding(
        approval_id=approval_id,
        schema_version=APPROVAL_ENVELOPE_SCHEMA_VERSION,
        tenant_id=str(run["client_id"]),
        principal_type=principal_type,
        principal_id=principal_id,
        workflow_id=str(run["id"]),
        active_graph_revision=int(run.get("active_graph_revision") or 1),
        task_id=str(action["id"]),
        action_id=str(action["id"]),
        capability_id=capability_id,
        tool_id=tool_id,
        effect_class=effect_class,
        native_target=native_target,
        input_hash=input_hash,
        payload_hash=payload_hash,
        evidence_digest=evidence_digest,
        authority_hash=authority_hash,
        registry_version=registry_version,
        registry_fingerprint=registry_fingerprint,
        harness_id=harness_id,
        harness_version=f"registry:{registry_fingerprint}:harness:{harness_id}",
        policy_profile_id=policy_profile_id,
        policy_version=(f"registry:{registry_fingerprint}:policy:{policy_profile_id}"),
        effect_idempotency_key=str(
            action.get("dedupe_key") or f"agent-action:{action['id']}:effect:v1"
        ),
        requested_at=requested_at,
        expires_at=expires_at,
    )


def _transition_for_command(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    envelope: ApprovalEnvelope,
    operation: str,
    occurred_at: datetime,
    approving_authority: ApprovalAuthority,
    revocation_reference: str | None,
    supersession_reference: str | None,
) -> ApprovalEnvelope:
    try:
        if operation == "approve":
            _validate_action_policy(run=run, action=action)
            return transition_approval(
                envelope,
                ApprovalStatus.APPROVED,
                occurred_at=occurred_at,
                approving_authority=approving_authority,
            )
        if operation == "reject":
            if envelope.status is ApprovalStatus.APPROVED:
                reference = revocation_reference or (
                    f"operator-rejection:{envelope.binding.approval_id}"
                )
                return transition_approval(
                    envelope,
                    ApprovalStatus.REVOKED,
                    occurred_at=occurred_at,
                    revocation_reference=reference,
                )
            return transition_approval(
                envelope,
                ApprovalStatus.REJECTED,
                occurred_at=occurred_at,
                approving_authority=approving_authority,
            )
        if operation == "revoke":
            return transition_approval(
                envelope,
                ApprovalStatus.REVOKED,
                occurred_at=occurred_at,
                revocation_reference=revocation_reference,
            )
        if operation == "expire":
            return transition_approval(
                envelope,
                ApprovalStatus.EXPIRED,
                occurred_at=occurred_at,
            )
        if operation == "supersede":
            if not supersession_reference:
                raise ApprovalLedgerError(
                    "supersede requires a replacement approval ID",
                    code="missing_supersession_reference",
                    status_code=400,
                )
            return transition_approval(
                envelope,
                ApprovalStatus.SUPERSEDED,
                occurred_at=occurred_at,
                supersession_reference=supersession_reference,
            )
    except ApprovalContractError as exc:
        raise ApprovalLedgerError(str(exc), code="invalid_approval_transition") from exc
    raise ApprovalLedgerError(
        f"unsupported approval command {operation!r}",
        code="unsupported_approval_command",
        status_code=400,
    )


def _validate_action_policy(*, run: Dict[str, Any], action: Dict[str, Any]) -> None:
    spec = get_capability_spec(str(action.get("capability_name") or ""))
    if not spec:
        return
    action_with_defaults = {
        **action,
        "tool_id": action.get("tool_id") or spec.tool_id,
        "effect_class": action.get("effect_class") or spec.effect_class,
    }
    try:
        PolicyEnforcer().validate_action_approval(
            run=run,
            action=action_with_defaults,
            spec=spec,
            inputs=spec.normalize_inputs(action.get("inputs") or {}),
        )
    except PolicyError as exc:
        raise ApprovalLedgerError(
            str(exc), code="approval_policy_rejected", status_code=400
        ) from exc


def _mutation(
    envelope: ApprovalEnvelope,
    *,
    sequence: int,
    expected_sequence: int | None,
    require_no_existing_action_approval: bool = False,
) -> Dict[str, Any]:
    return {
        "approval_id": envelope.binding.approval_id,
        "action_id": envelope.binding.action_id,
        "sequence": sequence,
        "expected_sequence": expected_sequence,
        "require_no_existing_action_approval": require_no_existing_action_approval,
        "event_type": f"approval_{envelope.status.value}",
        "status": envelope.status.value,
        "envelope": approval_envelope_payload(envelope),
        "envelope_digest": approval_envelope_digest(envelope),
        "occurred_at": _format_datetime(envelope.transitioned_at),
    }


def _approval_projection(
    envelope: ApprovalEnvelope, *, sequence: int
) -> Dict[str, Any]:
    return {
        "approval_id": envelope.binding.approval_id,
        "tenant_id": envelope.binding.tenant_id,
        "workflow_id": envelope.binding.workflow_id,
        "action_id": envelope.binding.action_id,
        "sequence": sequence,
        "status": envelope.status.value,
        "envelope": approval_envelope_payload(envelope),
        "envelope_digest": approval_envelope_digest(envelope),
    }


def _audit_events(
    *,
    run: Dict[str, Any],
    action: Dict[str, Any],
    command_id: str,
    envelope: ApprovalEnvelope,
    envelope_digest: str,
    operation: str,
    audit_context: str,
) -> list[Dict[str, Any]]:
    authority = envelope.approving_authority
    base = {
        "event_type": f"approval_{envelope.status.value}",
        "status": envelope.status.value,
        "sequence": int(action.get("sequence") or 0),
        "capability_name": action.get("capability_name"),
        "capability_version": action.get("capability_version"),
        "tool_id": action.get("tool_id"),
        "skill_id": action.get("skill_id"),
        "effect_class": action.get("effect_class"),
        "trace_id": run.get("trace_id"),
        "note": f"Durable approval command: {operation}",
        "anchors": {
            "approval_id": envelope.binding.approval_id,
            "approval_sequence": None,
            "approval_envelope_digest": envelope_digest,
            "approval_status": envelope.status.value,
            "approval_command_id": command_id,
            "approving_authority": None
            if authority is None
            else _authority_payload(authority),
            "effect_idempotency_key": envelope.binding.effect_idempotency_key,
        },
    }
    if audit_context != "operator_command":
        compatibility = dict(base)
        compatibility["event_type"] = (
            "action_approved"
            if envelope.status is ApprovalStatus.APPROVED
            else "action_rejected"
            if envelope.status in {ApprovalStatus.REJECTED, ApprovalStatus.REVOKED}
            else base["event_type"]
        )
        return (
            [base]
            if compatibility["event_type"] == base["event_type"]
            else [base, compatibility]
        )
    received = dict(base)
    received["event_type"] = f"operator_command_{operation}"
    received["status"] = "received"
    completed = dict(received)
    completed["status"] = "completed"
    compatibility = dict(base)
    compatibility["event_type"] = (
        "action_approved"
        if envelope.status is ApprovalStatus.APPROVED
        else "action_rejected"
    )
    return [received, base, compatibility, completed]


def _command_response(
    *, deps: AppDeps, command: Dict[str, Any], replayed: bool
) -> Dict[str, Any]:
    result = dict(command.get("result") or {})
    result_hash = result.pop("result_hash", None)
    if (
        not _is_digest(result_hash)
        or result_hash != command.get("result_hash")
        or _hash_payload(result) != result_hash
    ):
        raise ApprovalLedgerError(
            "stored approval command result failed integrity validation",
            code="corrupt_approval_command",
            status_code=500,
        )
    action = deps.agent_actions.get_agent_action(
        action_id=command["action_id"], client_id=command["tenant_id"]
    )
    return {
        "approval": dict(command.get("result", {}).get("approval") or {}),
        "decision": command.get("result", {}).get("decision"),
        "command": command,
        "action": action,
        "replayed": replayed,
    }


def _parse_stored_envelope(row: Dict[str, Any]) -> ApprovalEnvelope:
    try:
        envelope = approval_envelope_from_payload(dict(row["envelope"]))
    except ApprovalContractError as exc:
        raise ApprovalLedgerError(
            "stored approval envelope failed canonical validation",
            code="corrupt_approval_record",
            status_code=500,
        ) from exc
    if approval_envelope_digest(envelope) != row["envelope_digest"]:
        raise ApprovalLedgerError(
            "stored approval envelope digest does not match its content",
            code="corrupt_approval_record",
            status_code=500,
        )
    return envelope


def _validate_record_history(*, deps: AppDeps, row: Dict[str, Any]) -> None:
    envelope = _parse_stored_envelope(row)
    events = deps.approval_ledger.list_approval_events(
        tenant_id=row["tenant_id"],
        workflow_id=row["workflow_id"],
        approval_id=row["approval_id"],
        limit=1000,
    )
    if not events:
        raise ApprovalLedgerError(
            "approval projection has no append-only history",
            code="corrupt_approval_history",
            status_code=500,
        )
    last = events[-1]
    try:
        event_envelope = approval_envelope_from_payload(dict(last["envelope"]))
    except ApprovalContractError as exc:
        raise ApprovalLedgerError(
            "approval event failed canonical validation",
            code="corrupt_approval_history",
            status_code=500,
        ) from exc
    if (
        approval_envelope_digest(event_envelope) != last["envelope_digest"]
        or int(last["sequence"]) != int(row["sequence"])
        or last["envelope_digest"] != row["envelope_digest"]
        or event_envelope != envelope
    ):
        raise ApprovalLedgerError(
            "approval projection diverges from append-only history",
            code="corrupt_approval_history",
            status_code=500,
        )


def _legacy_action_projection(status: ApprovalStatus) -> str | None:
    if status is ApprovalStatus.APPROVED:
        return "approved"
    if status in {
        ApprovalStatus.REJECTED,
        ApprovalStatus.EXPIRED,
        ApprovalStatus.REVOKED,
        ApprovalStatus.SUPERSEDED,
    }:
        return "rejected"
    return None


def _approval_ttl(*, run: Dict[str, Any], requested: int | None) -> int:
    policy = run.get("approval_policy") or {}
    configured = requested
    if configured is None and isinstance(policy, dict):
        configured = policy.get("approval_ttl_seconds")
    if configured is None:
        ttl = DEFAULT_APPROVAL_TTL_SECONDS
    elif type(configured) is not int:
        raise ApprovalLedgerError(
            "approval TTL must be an exact integer",
            code="invalid_approval_ttl",
            status_code=400,
        )
    else:
        ttl = configured
    if ttl < 1 or ttl > MAX_APPROVAL_TTL_SECONDS:
        raise ApprovalLedgerError(
            f"approval TTL must be between 1 and {MAX_APPROVAL_TTL_SECONDS} seconds",
            code="invalid_approval_ttl",
            status_code=400,
        )
    return ttl


def _require_scope(
    *, run: Dict[str, Any], action: Dict[str, Any]
) -> tuple[str, str, str]:
    tenant_id = _require_canonical_identifier("tenant_id", run.get("client_id"))
    workflow_id = _require_canonical_identifier("workflow_id", run.get("id"))
    action_id = _require_canonical_identifier("action_id", action.get("id"))
    if str(action.get("agent_run_id") or "") != workflow_id:
        raise ApprovalLedgerError(
            "governed action does not belong to the workflow",
            code="action_scope_mismatch",
            status_code=404,
        )
    return tenant_id, workflow_id, action_id


def _reload_authoritative_scope(
    *,
    deps: AppDeps,
    tenant_id: str,
    workflow_id: str,
    action_id: str,
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    run = deps.agent_runs.get_agent_run(run_id=workflow_id, client_id=tenant_id)
    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=tenant_id
    )
    if not run or not action or action.get("agent_run_id") != workflow_id:
        raise ApprovalLedgerError(
            "governed action no longer exists in the trusted workflow scope",
            code="action_scope_mismatch",
            status_code=404,
        )
    return run, action


def _normalize_operation(value: object) -> str:
    if type(value) is not str:
        raise ApprovalLedgerError(
            "approval command must be an exact string",
            code="unsupported_approval_command",
            status_code=400,
        )
    normalized = value.strip().lower()
    if value != normalized or normalized not in SUPPORTED_APPROVAL_COMMANDS:
        raise ApprovalLedgerError(
            "unsupported approval command",
            code="unsupported_approval_command",
            status_code=400,
        )
    return normalized


def _require_canonical_identifier(field_name: str, value: object) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ApprovalLedgerError(
            f"{field_name} must be a non-empty canonical string",
            code=f"invalid_{field_name}",
            status_code=400,
        )
    return value


def _optional_identifier(field_name: str, value: object) -> str | None:
    if value is None:
        return None
    return _require_canonical_identifier(field_name, value)


def _principal_type(value: object) -> PrincipalType:
    normalized = str(value or "human").strip().lower()
    try:
        return PrincipalType(normalized)
    except ValueError as exc:
        raise ApprovalLedgerError(
            f"unsupported requesting principal type {normalized!r}",
            code="invalid_principal_type",
            status_code=400,
        ) from exc


def _authority_payload(authority: ApprovalAuthority) -> Dict[str, str]:
    return {
        "principal_type": authority.principal_type.value,
        "principal_id": authority.principal_id,
        "authority_source": authority.authority_source,
        "authority_version": authority.authority_version,
    }


def _hash_payload(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _is_digest(value: object) -> bool:
    return (
        type(value) is str
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _normalize_utc(value: datetime) -> datetime:
    if type(value) is not datetime or value.tzinfo is None:
        raise ApprovalLedgerError(
            "occurred_at must be an aware built-in datetime",
            code="invalid_occurred_at",
            status_code=400,
        )
    if type(value.tzinfo) is not timezone:
        raise ApprovalLedgerError(
            "occurred_at must use a built-in fixed-offset timezone",
            code="invalid_occurred_at",
            status_code=400,
        )
    return value.astimezone(timezone.utc)


def _format_datetime(value: datetime) -> str:
    return value.isoformat(timespec="microseconds").replace("+00:00", "Z")


__all__ = [
    "ApprovalLedgerError",
    "DECIDABLE_ACTION_STATUSES",
    "DEFAULT_APPROVAL_TTL_SECONDS",
    "MAX_APPROVAL_TTL_SECONDS",
    "SUPPORTED_APPROVAL_COMMANDS",
    "build_action_approval_binding",
    "get_authoritative_approval",
    "issue_action_approval_command",
    "list_action_approvals",
]
