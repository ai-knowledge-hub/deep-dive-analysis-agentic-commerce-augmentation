from __future__ import annotations

from typing import Any, Dict

from application.ports.deps import AppDeps


def claim_next_approved_action(*, deps: AppDeps, run_id: str) -> Dict[str, Any] | None:
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=500)
    for item in (row for row in actions if row.get("status") == "approved"):
        claimed = deps.agent_actions.transition_agent_action_status(
            action_id=str(item.get("id") or ""),
            from_status="approved",
            to_status="executing",
        )
        if claimed:
            return claimed
    return None


__all__ = ["claim_next_approved_action"]
