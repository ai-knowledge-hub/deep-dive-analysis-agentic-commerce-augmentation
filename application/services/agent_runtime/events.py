from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from application.ports.deps import AppDeps


@dataclass(frozen=True)
class AgentRunEvent:
    id: str
    run_id: str
    action_id: Optional[str]
    sequence: int
    event_type: str
    status: str
    capability_name: Optional[str]
    capability_version: Optional[str]
    timestamp: Optional[str]
    note: Optional[str]
    is_policy_event: bool
    anchors: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def list_agent_run_events(
    *,
    deps: AppDeps,
    run_id: str,
    limit: int = 500,
    event_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    run = deps.agent_runs.get_agent_run(run_id=run_id)
    if not run:
        raise ValueError("Agent run not found")
    rows = deps.agent_events.list_agent_events(
        agent_run_id=run_id,
        event_type=event_type,
        limit=limit,
    )
    events = [
        AgentRunEvent(
            id=str(item.get("id") or ""),
            run_id=str(item.get("run_id") or run_id),
            action_id=item.get("action_id"),
            sequence=int(item.get("sequence") or 0),
            event_type=str(item.get("event_type") or ""),
            status=str(item.get("status") or "unknown"),
            capability_name=item.get("capability_name"),
            capability_version=item.get("capability_version"),
            timestamp=item.get("timestamp"),
            note=item.get("note"),
            is_policy_event=bool(item.get("is_policy_event")),
            anchors=dict(item.get("anchors") or {}),
        )
        for item in rows
    ]
    return [item.to_dict() for item in events]


__all__ = ["list_agent_run_events", "AgentRunEvent"]
