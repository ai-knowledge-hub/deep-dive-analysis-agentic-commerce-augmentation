from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_ledger import ApprovalLedgerError
from application.services.agent_runtime.commands.context import (
    AgentRunCommandError,
    command_context,
)
from application.services.agent_runtime.commands.decisions import (
    apply_command_action_decision,
)
from application.services.agent_runtime.commands.preflight import (
    _command_preflight,
    _record_command_event,
)
from application.services.agent_runtime.commands.recovery import (
    create_change_plan_recovery_action,
    create_retry_action,
)
from application.services.agent_runtime.effect_recovery import (
    EffectRecoveryError,
    reconcile_effect_from_durable_evidence,
)
from application.services.agent_runtime.runtime import (
    AgentRuntimeService,
)
from domain.workflow.approval import ApprovalAuthority


def preflight_agent_run_command(
    *,
    deps: AppDeps,
    run_id: str,
    client_id: str,
    command_type: str,
    action_id: Optional[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    run, action, normalized_command = command_context(
        deps=deps,
        run_id=run_id,
        client_id=client_id,
        command_type=command_type,
        action_id=action_id,
    )
    return {
        "preflight": _command_preflight(
            deps=deps,
            run=run,
            command_type=normalized_command,
            action=action,
            metadata=metadata,
        ),
        "run": run,
        "action": action,
    }


def issue_agent_run_command(
    *,
    deps: AppDeps,
    runtime: AgentRuntimeService,
    run_id: str,
    client_id: str,
    user_id: Optional[str],
    command_type: str,
    action_id: Optional[str],
    message: Optional[str],
    metadata: Dict[str, Any],
    approving_authority: ApprovalAuthority | None = None,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    run, action, normalized_command = command_context(
        deps=deps,
        run_id=run_id,
        client_id=client_id,
        command_type=command_type,
        action_id=action_id,
    )
    preflight = _command_preflight(
        deps=deps,
        run=run,
        command_type=normalized_command,
        action=action,
        metadata=metadata,
    )
    if not preflight["allowed"] and normalized_command not in {"approve", "reject"}:
        raise AgentRunCommandError(status_code=409, detail=preflight)

    if normalized_command in {"approve", "reject"}:
        result = {"run": run, "preflight": preflight}
        _apply_agent_run_command(
            deps=deps,
            runtime=runtime,
            result=result,
            run_id=run_id,
            run=run,
            action=action,
            command_type=normalized_command,
            command_receipt={},
            user_id=user_id,
            message=message,
            metadata=metadata,
            approving_authority=approving_authority,
            idempotency_key=idempotency_key,
        )
        ledger_command = dict(result.get("approval_command") or {})
        if result.get("approval_replayed"):
            result["preflight"] = {
                **preflight,
                "allowed": True,
                "blockers": [],
                "replayed": True,
            }
        result["command"] = {
            "id": ledger_command.get("command_id"),
            "event_type": f"operator_command_{normalized_command}",
            "status": "received",
            "anchors": {
                "approval_id": ledger_command.get("approval_id"),
                "approval_command_id": ledger_command.get("command_id"),
                "approval_result_hash": ledger_command.get("result_hash"),
            },
        }
        return result

    receipt = _record_command_event(
        deps=deps,
        run=run,
        command_type=normalized_command,
        status="received",
        action=action,
        note=message or f"Operator chat command: {normalized_command}",
        metadata=metadata,
        command_authority=approving_authority,
    )
    result: Dict[str, Any] = {
        "command": receipt,
        "run": run,
        "preflight": preflight,
    }

    if normalized_command in {"explain", "focus"}:
        return result

    _apply_agent_run_command(
        deps=deps,
        runtime=runtime,
        result=result,
        run_id=run_id,
        run=run,
        action=action,
        command_type=normalized_command,
        command_receipt=receipt,
        user_id=user_id,
        message=message,
        metadata=metadata,
        approving_authority=approving_authority,
        idempotency_key=idempotency_key,
    )

    _record_command_event(
        deps=deps,
        run=result.get("run") or run,
        command_type=normalized_command,
        status="completed",
        action=result.get("action") or action,
        note=f"Operator chat command completed: {normalized_command}",
        metadata=metadata,
        command_authority=approving_authority,
    )
    return result


def _apply_agent_run_command(
    *,
    deps: AppDeps,
    runtime: AgentRuntimeService,
    result: Dict[str, Any],
    run_id: str,
    run: Dict[str, Any],
    action: Optional[Dict[str, Any]],
    command_type: str,
    command_receipt: Dict[str, Any],
    user_id: Optional[str],
    message: Optional[str],
    metadata: Dict[str, Any],
    approving_authority: ApprovalAuthority | None,
    idempotency_key: str | None,
) -> None:
    if command_type == "change_plan":
        result["action"] = create_change_plan_recovery_action(
            deps=deps,
            run_id=run_id,
            run=run,
            source_action=action,
            command_receipt=command_receipt,
            message=message,
            metadata=metadata,
        )
    elif command_type == "start":
        runtime_result = runtime.start_run(run_id=run_id)
        result["run"] = runtime_result.run
        result["message"] = runtime_result.message
    elif command_type == "pause":
        runtime_result = runtime.pause_run(run_id=run_id)
        result["run"] = runtime_result.run
    elif command_type == "cancel":
        runtime_result = runtime.cancel_run(run_id=run_id)
        result["run"] = runtime_result.run
    elif command_type == "step":
        runtime_result = runtime.step_once(run_id=run_id, user_id=user_id)
        result["run"] = runtime_result.run
        result["action"] = runtime_result.action
    elif command_type == "retry":
        if not action:
            raise AgentRunCommandError(status_code=400, detail="Action id is required")
        result["action"] = create_retry_action(
            deps=deps,
            run_id=run_id,
            run=run,
            action=action,
            metadata=metadata,
        )
    elif command_type == "reconcile_effect":
        if not action:
            raise AgentRunCommandError(status_code=400, detail="Action id is required")
        if approving_authority is None:
            raise AgentRunCommandError(
                status_code=401,
                detail="Effect reconciliation requires authenticated authority",
            )
        try:
            result.update(
                reconcile_effect_from_durable_evidence(
                    deps=deps,
                    run=run,
                    action=action,
                )
            )
        except EffectRecoveryError as exc:
            raise AgentRunCommandError(
                status_code=exc.status_code,
                detail={
                    "code": exc.code,
                    "message": str(exc),
                    "mismatches": list(exc.mismatches),
                },
            ) from exc
    elif command_type in {"approve", "reject"}:
        if not action:
            raise AgentRunCommandError(status_code=400, detail="Action id is required")
        if approving_authority is None:
            raise AgentRunCommandError(
                status_code=401,
                detail="Approval command requires authenticated authority",
            )
        try:
            approval_result = apply_command_action_decision(
                deps=deps,
                run_id=run_id,
                run=run,
                action=action,
                command_type=command_type,
                approving_authority=approving_authority,
                idempotency_key=idempotency_key
                or f"operator-command:{run_id}:{action['id']}:{command_type}",
                message=message,
                metadata=metadata,
            )
        except ApprovalLedgerError as exc:
            raise AgentRunCommandError(
                status_code=exc.status_code,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        result["action"] = approval_result.get("action") or action
        result["approval"] = approval_result.get("approval")
        result["approval_command"] = approval_result.get("command")
        result["approval_replayed"] = bool(approval_result.get("replayed"))
