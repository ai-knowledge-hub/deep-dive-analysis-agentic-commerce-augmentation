from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_ledger import issue_action_approval_command
from domain.workflow.approval import ApprovalAuthority


def apply_command_action_decision(
    *,
    deps: AppDeps,
    run_id: str,
    run: Dict[str, Any],
    action: Dict[str, Any],
    command_type: str,
    approving_authority: ApprovalAuthority,
    idempotency_key: str,
    message: str | None,
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    del run_id
    return issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type=command_type,
        approving_authority=approving_authority,
        idempotency_key=idempotency_key,
        audit_context="operator_command",
        command_context_digest=_command_context_digest(
            message=message, metadata=metadata
        ),
    )


def _command_context_digest(
    *, message: str | None, metadata: Dict[str, Any]
) -> str:
    encoded = json.dumps(
        {"message": message, "metadata": metadata},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def decide_agent_action(
    *,
    deps: AppDeps,
    action_id: str,
    client_id: str,
    user_id: Optional[str],
    decision: str,
    approving_authority: ApprovalAuthority,
    idempotency_key: str | None = None,
) -> Dict[str, Any]:
    """Compatibility entry point backed by the durable approval ledger."""

    action = deps.agent_actions.get_agent_action(
        action_id=action_id, client_id=client_id
    )
    if not action:
        raise ValueError("Agent action not found")
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision not in {"approve", "reject"}:
        raise ValueError("Invalid decision")
    run = deps.agent_runs.get_agent_run(
        run_id=str(action.get("agent_run_id") or ""), client_id=client_id
    )
    if not run:
        raise ValueError("Agent run not found")
    del user_id
    response = issue_action_approval_command(
        deps=deps,
        run=run,
        action=action,
        command_type=normalized_decision,
        approving_authority=approving_authority,
        idempotency_key=idempotency_key
        or f"legacy-action-decision:{action_id}:{normalized_decision}",
    )
    current = response.get("action")
    return current if isinstance(current, dict) else action


__all__ = ["apply_command_action_decision", "decide_agent_action"]
