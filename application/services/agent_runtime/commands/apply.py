"""Command-specific mutations for the agent-run command service."""

from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_ledger import ApprovalLedgerError
from application.services.agent_runtime.commands.context import AgentRunCommandError
from application.services.agent_runtime.commands.decisions import (
    apply_command_action_decision,
)
from application.services.agent_runtime.commands.recovery import (
    RecoveryActionCreationError,
    create_change_plan_recovery_action,
    create_retry_action,
)
from application.services.agent_runtime.effect_recovery import (
    EffectRecoveryError,
    reconcile_effect_from_durable_evidence,
)
from application.services.agent_runtime.runtime import AgentRuntimeService
from domain.workflow.approval import ApprovalAuthority


def apply_agent_run_command(
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
        try:
            result["action"] = create_change_plan_recovery_action(
                deps=deps,
                run_id=run_id,
                run=run,
                source_action=action,
                command_receipt=command_receipt,
                message=message,
                metadata=metadata,
            )
        except RecoveryActionCreationError as exc:
            raise AgentRunCommandError(
                status_code=409,
                detail={"code": "run_terminal", "message": str(exc)},
            ) from exc
    elif command_type == "start":
        runtime_result = runtime.start_run(run_id=run_id)
        result["run"] = runtime_result.run
        result["message"] = runtime_result.message
    elif command_type == "pause":
        result["run"] = runtime.pause_run(run_id=run_id).run
    elif command_type == "cancel":
        result["run"] = runtime.cancel_run(run_id=run_id).run
    elif command_type == "step":
        runtime_result = runtime.step_once(run_id=run_id, user_id=user_id)
        result["run"] = runtime_result.run
        result["action"] = runtime_result.action
    elif command_type == "retry":
        if not action:
            raise AgentRunCommandError(status_code=400, detail="Action id is required")
        try:
            result["action"] = create_retry_action(
                deps=deps,
                run_id=run_id,
                run=run,
                action=action,
                metadata=metadata,
            )
        except RecoveryActionCreationError as exc:
            raise AgentRunCommandError(
                status_code=409,
                detail={"code": "run_terminal", "message": str(exc)},
            ) from exc
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


__all__ = ["apply_agent_run_command"]
