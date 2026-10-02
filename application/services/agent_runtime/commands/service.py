from __future__ import annotations

from collections.abc import Callable
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.commands.apply import apply_agent_run_command
from application.services.agent_runtime.commands.context import (
    AgentRunCommandError,
    command_context,
)
from application.services.agent_runtime.commands.preflight import (
    _command_preflight,
    _record_command_event,
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
    conversation_proposal: Dict[str, Any] | None = None,
    conversation_preflight: Dict[str, Any] | None = None,
    conversation_principal_id: str | None = None,
    conversation_confirmation_state: Callable[[], Dict[str, Any]] | None = None,
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
    if (
        conversation_proposal is None
        and not preflight["allowed"]
        and normalized_command not in {"approve", "reject"}
    ):
        raise AgentRunCommandError(status_code=409, detail=preflight)

    if conversation_proposal is not None:
        if (
            normalized_command != "pause"
            or conversation_preflight is None
            or not conversation_principal_id
            or conversation_confirmation_state is None
        ):
            raise AgentRunCommandError(
                status_code=400,
                detail={
                    "code": "invalid_conversation_proposal",
                    "message": "Only an exact conversational pause proposal is supported.",
                },
            )
        receipt = deps.operator_commands.commit_pause(
            proposal=conversation_proposal,
            principal_id=conversation_principal_id,
            confirmation_state=conversation_confirmation_state,
        )
        updated_run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
        return {
            "command": {
                "id": receipt["event_ids"]["command"],
                "event_type": "operator_command_pause",
                "status": "completed",
                "anchors": {
                    "proposal_id": receipt["proposal_id"],
                    "proposal_digest": receipt["proposal_digest"],
                    "receipt_id": receipt["receipt_id"],
                },
            },
            "command_receipt": receipt,
            "run": updated_run or run,
            "preflight": conversation_preflight,
        }

    if normalized_command in {"approve", "reject"}:
        result = {"run": run, "preflight": preflight}
        apply_agent_run_command(
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

    apply_agent_run_command(
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
