from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps


SUPPORTED_COMMANDS = {
    "explain",
    "focus",
    "change_plan",
    "start",
    "pause",
    "cancel",
    "step",
    "approve",
    "reject",
    "reconcile_effect",
    "retry",
}


class AgentRunCommandError(Exception):
    def __init__(self, *, status_code: int, detail: Any) -> None:
        super().__init__(str(detail))
        self.status_code = status_code
        self.detail = detail


def command_context(
    *,
    deps: AppDeps,
    run_id: str,
    client_id: str,
    command_type: str,
    action_id: Optional[str],
) -> tuple[Dict[str, Any], Optional[Dict[str, Any]], str]:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise AgentRunCommandError(status_code=404, detail="Agent run not found")

    normalized_command = str(command_type or "").strip().lower()
    if normalized_command not in SUPPORTED_COMMANDS:
        raise AgentRunCommandError(status_code=400, detail="Unsupported command")

    action = None
    if action_id:
        action = deps.agent_actions.get_agent_action(
            action_id=action_id,
            client_id=client_id,
        )
        if not action or str(action.get("agent_run_id") or "") != run_id:
            raise AgentRunCommandError(status_code=404, detail="Agent action not found")
    return run, action, normalized_command


__all__ = ["AgentRunCommandError", "SUPPORTED_COMMANDS", "command_context"]
