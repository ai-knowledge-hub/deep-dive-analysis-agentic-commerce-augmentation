from __future__ import annotations

import base64
import json
from datetime import datetime
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


@dataclass(frozen=True)
class AgentRunEventPage:
    events: List[AgentRunEvent]
    before_cursor: Optional[str]
    after_cursor: Optional[str]
    has_more_before: bool
    has_more_after: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "events": [event.to_dict() for event in self.events],
            "page": {
                "before_cursor": self.before_cursor,
                "after_cursor": self.after_cursor,
                "has_more_before": self.has_more_before,
                "has_more_after": self.has_more_after,
            },
        }


def list_agent_run_events(
    *,
    deps: AppDeps,
    run_id: str,
    limit: int = 500,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    capability_name: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
) -> List[Dict[str, Any]]:
    page = list_agent_run_events_page(
        deps=deps,
        run_id=run_id,
        limit=limit,
        event_type=event_type,
        status=status,
        capability_name=capability_name,
        since=since,
        until=until,
    )
    return [event.to_dict() for event in page.events]


def list_agent_run_events_page(
    *,
    deps: AppDeps,
    run_id: str,
    client_id: Optional[str] = None,
    limit: int = 500,
    event_type: Optional[str] = None,
    status: Optional[str] = None,
    capability_name: Optional[str] = None,
    since: Optional[str] = None,
    until: Optional[str] = None,
    before: Optional[str] = None,
    after: Optional[str] = None,
    event_id: Optional[str] = None,
    around: int = 120,
) -> AgentRunEventPage:
    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=client_id)
    if not run:
        raise ValueError("Agent run not found")
    if event_id:
        anchor_row = deps.agent_events.get_agent_event(event_id=event_id)
        if not anchor_row or str(anchor_row.get("run_id") or "") != run_id:
            raise ValueError("Agent event not found")
        anchor_event = _to_event(anchor_row, run_id=run_id)
        if not _matches_filters(
            anchor_event,
            event_type=event_type,
            status=status,
            capability_name=capability_name,
            since=since,
            until=until,
        ):
            raise ValueError("Agent event not found in current filters")
        around_limit = max(1, min(int(around), 2000))
        before_limit = (around_limit - 1) // 2
        after_limit = (around_limit - 1) - before_limit
        older_rows = (
            deps.agent_events.list_agent_events(
                agent_run_id=run_id,
                event_type=event_type,
                status=status,
                capability_name=capability_name,
                since=since,
                until=until,
                limit=before_limit,
                before={
                    "created_at": anchor_event.timestamp or "",
                    "id": anchor_event.id,
                },
            )
            if before_limit > 0
            else []
        )
        newer_rows = (
            deps.agent_events.list_agent_events(
                agent_run_id=run_id,
                event_type=event_type,
                status=status,
                capability_name=capability_name,
                since=since,
                until=until,
                limit=after_limit,
                after={
                    "created_at": anchor_event.timestamp or "",
                    "id": anchor_event.id,
                },
            )
            if after_limit > 0
            else []
        )
        events = [
            *[_to_event(item, run_id=run_id) for item in older_rows],
            anchor_event,
            *[_to_event(item, run_id=run_id) for item in newer_rows],
        ]
    else:
        before_anchor = _decode_cursor(before)
        after_anchor = _decode_cursor(after)
        rows = deps.agent_events.list_agent_events(
            agent_run_id=run_id,
            event_type=event_type,
            status=status,
            capability_name=capability_name,
            since=since,
            until=until,
            limit=limit,
            before=before_anchor,
            after=after_anchor,
        )
        events = [_to_event(item, run_id=run_id) for item in rows]
    before_cursor = _encode_cursor(events[0]) if events else None
    after_cursor = _encode_cursor(events[-1]) if events else None

    has_more_before = False
    has_more_after = False
    if events:
        older_probe = deps.agent_events.list_agent_events(
            agent_run_id=run_id,
            event_type=event_type,
            status=status,
            capability_name=capability_name,
            since=since,
            until=until,
            limit=1,
            before={"created_at": events[0].timestamp or "", "id": events[0].id},
        )
        has_more_before = len(older_probe) > 0
        newer_probe = deps.agent_events.list_agent_events(
            agent_run_id=run_id,
            event_type=event_type,
            status=status,
            capability_name=capability_name,
            since=since,
            until=until,
            limit=1,
            after={"created_at": events[-1].timestamp or "", "id": events[-1].id},
        )
        has_more_after = len(newer_probe) > 0

    return AgentRunEventPage(
        events=events,
        before_cursor=before_cursor,
        after_cursor=after_cursor,
        has_more_before=has_more_before,
        has_more_after=has_more_after,
    )


def _encode_cursor(event: AgentRunEvent) -> Optional[str]:
    if not event.timestamp or not event.id:
        return None
    payload = {"created_at": event.timestamp, "id": event.id}
    raw = json.dumps(payload, sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _decode_cursor(cursor: Optional[str]) -> Optional[Dict[str, str]]:
    if not cursor:
        return None
    try:
        data = base64.urlsafe_b64decode(cursor.encode("utf-8"))
        parsed = json.loads(data.decode("utf-8"))
        created_at = str(parsed.get("created_at") or "")
        event_id = str(parsed.get("id") or "")
        if not created_at or not event_id:
            return None
        return {"created_at": created_at, "id": event_id}
    except Exception:
        return None


def _to_event(item: Dict[str, Any], *, run_id: str) -> AgentRunEvent:
    return AgentRunEvent(
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


def _to_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _matches_filters(
    event: AgentRunEvent,
    *,
    event_type: Optional[str],
    status: Optional[str],
    capability_name: Optional[str],
    since: Optional[str],
    until: Optional[str],
) -> bool:
    if event_type and event_type not in {"all", ""}:
        if event_type == "policy" and not event.is_policy_event:
            return False
        if event_type in {"failed", "executed"} and event.status != event_type:
            return False
    if status and status not in {"all", ""} and event.status != status:
        return False
    if (
        capability_name
        and capability_name not in {"all", ""}
        and (event.capability_name or "") != capability_name
    ):
        return False
    event_dt = _to_dt(event.timestamp)
    since_dt = _to_dt(since)
    until_dt = _to_dt(until)
    if since_dt and event_dt and event_dt < since_dt:
        return False
    if until_dt and event_dt and event_dt > until_dt:
        return False
    return True


__all__ = [
    "list_agent_run_events",
    "list_agent_run_events_page",
    "AgentRunEvent",
    "AgentRunEventPage",
]
