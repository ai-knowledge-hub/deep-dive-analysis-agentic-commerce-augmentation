from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
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
    actions = deps.agent_actions.list_agent_actions(agent_run_id=run_id, limit=limit)
    events: List[AgentRunEvent] = []
    for action in actions:
        status = str(action.get("status") or "unknown").strip().lower()
        note = (action.get("error") or action.get("rationale") or None) and str(
            action.get("error") or action.get("rationale") or ""
        )
        outputs = action.get("outputs") or {}
        metric_id = None
        if isinstance(outputs, dict):
            metric_id = (
                outputs.get("metric_id")
                or outputs.get("new_metric_id")
                or outputs.get("source_metric_id")
            )
        event = AgentRunEvent(
            id=f"evt:{action.get('id') or ''}",
            run_id=run_id,
            action_id=str(action.get("id") or "") or None,
            sequence=int(action.get("sequence") or 0),
            event_type=f"action_{status}",
            status=status,
            capability_name=str(action.get("capability_name") or "") or None,
            capability_version=str(action.get("capability_version") or "") or None,
            timestamp=(action.get("updated_at") or action.get("created_at")) and str(
                action.get("updated_at") or action.get("created_at")
            ),
            note=note,
            is_policy_event=_is_policy_text(note),
            anchors={
                "experiment_id": run.get("experiment_id"),
                "variant_id": action.get("variant_id"),
                "validation_job_id": action.get("validation_job_id"),
                "hypothesis_id": action.get("hypothesis_id"),
                "snapshot_version": action.get("snapshot_version"),
                "metric_id": metric_id,
            },
        )
        events.append(event)

    events.sort(
        key=lambda item: (
            _parse_timestamp(item.timestamp),
            item.sequence,
        )
    )
    filtered = _apply_event_filter(events, event_type=event_type)
    return [item.to_dict() for item in filtered]


def _parse_timestamp(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _is_policy_text(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = str(text).lower()
    return any(
        token in lowered
        for token in ("budget", "policy", "required", "not allowed", "guardrail")
    )


def _apply_event_filter(
    events: List[AgentRunEvent], event_type: Optional[str]
) -> List[AgentRunEvent]:
    mode = str(event_type or "all").strip().lower()
    if mode in {"", "all"}:
        return events
    if mode == "policy":
        return [item for item in events if item.is_policy_event]
    if mode == "failed":
        return [item for item in events if item.status == "failed"]
    if mode == "executed":
        return [item for item in events if item.status == "executed"]
    return events


__all__ = ["list_agent_run_events", "AgentRunEvent"]
