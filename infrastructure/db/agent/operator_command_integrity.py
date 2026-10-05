"""Shared locked integrity checks for conversational command ledgers."""

import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Any

from domain.workflow.operator_commands import OperatorCommandConflictError


def _require_run_fence(row: sqlite3.Row, source: dict[str, Any]) -> None:
    expected = {
        "status": source["run_status"],
        "state": source["run_state"],
        "active_graph_revision": source["active_graph_revision"],
        "harness_id": source["harness_id"],
        "policy_profile_id": source["policy_profile_id"],
        "registry_version": source["registry_version"],
        "registry_fingerprint": source["registry_fingerprint"],
    }
    if "run_mode" in source:
        expected["run_mode"] = source["run_mode"]
    if any(row[field] != value for field, value in expected.items()):
        raise OperatorCommandConflictError(
            "run_changed",
            "The run lifecycle, revision, or governing pins changed. Ask again for a fresh command proposal.",
        )
    if row["lock_token"]:
        raise OperatorCommandConflictError(
            "run_busy",
            "The run acquired in-flight work before command committed. Wait for it to settle and ask again.",
        )


def _require_snapshot_digest(proposal: dict[str, Any], observed: Any) -> None:
    if observed != proposal["source"]["snapshot_digest"]:
        raise OperatorCommandConflictError(
            "snapshot_changed",
            "The run evidence changed after this command proposal. Ask again for a fresh proposal.",
        )


def _require_event_head(conn: sqlite3.Connection, proposal: dict[str, Any]) -> None:
    row = conn.execute(
        """
        SELECT id, created_at FROM agent_events
        WHERE agent_run_id = ?
        ORDER BY created_at DESC, id DESC
        LIMIT 1
        """,
        (proposal["run_id"],),
    ).fetchone()
    source = proposal["source"]
    observed = (row["id"], row["created_at"]) if row is not None else (None, None)
    expected = (source["latest_event_id"], source["latest_event_timestamp"])
    if observed != expected:
        raise OperatorCommandConflictError(
            "event_cursor_changed",
            "The run event history changed. Ask again for a fresh command proposal.",
        )


def _insert_event(
    conn: sqlite3.Connection,
    *,
    event_id: str,
    run_row: sqlite3.Row,
    event_type: str,
    status: str,
    principal_id: str,
    note: str,
    anchors: dict[str, Any],
) -> None:
    latest = conn.execute(
        "SELECT MAX(created_at) AS timestamp FROM agent_events WHERE agent_run_id = ?",
        (run_row["id"],),
    ).fetchone()["timestamp"]
    timestamp = datetime.now(timezone.utc)
    if latest:
        previous = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        if previous.tzinfo is None:
            previous = previous.replace(tzinfo=timezone.utc)
        timestamp = max(timestamp, previous + timedelta(microseconds=1))
    created_at = timestamp.strftime("%Y-%m-%d %H:%M:%S.%f")
    conn.execute(
        """
        INSERT INTO agent_events (
            id, agent_run_id, action_id, sequence, event_type, status,
            capability_name, capability_version, principal_type, principal_id,
            tool_id, skill_id, effect_class, trace_id, note_text,
            is_policy_event, anchors_json, created_at
        ) VALUES (?, ?, NULL, 0, ?, ?, NULL, NULL, 'human', ?, NULL, NULL,
                  NULL, ?, ?, 0, json(?), ?)
        """,
        (
            event_id,
            run_row["id"],
            event_type,
            status,
            principal_id,
            run_row["trace_id"],
            note,
            _json(anchors),
            created_at,
        ),
    )


def _require_proposal_row_matches(row: sqlite3.Row, proposal: dict[str, Any]) -> None:
    source = proposal["source"]
    expected = {
        "proposal_id": proposal["proposal_id"],
        "tenant_id": proposal["tenant_id"],
        "workflow_id": proposal["run_id"],
        "principal_id": proposal["principal_id"],
        "command_type": proposal["command_type"],
        "proposal_digest": proposal["proposal_digest"],
        "active_graph_revision": source["active_graph_revision"],
        "source_run_status": source["run_status"],
        "source_run_state": source["run_state"],
        "snapshot_digest": source["snapshot_digest"],
        "snapshot_cursor": source["snapshot_cursor"],
        "latest_event_id": source["latest_event_id"],
        "latest_event_timestamp": source["latest_event_timestamp"],
        "harness_id": source["harness_id"],
        "policy_profile_id": source["policy_profile_id"],
        "registry_version": source["registry_version"],
        "registry_fingerprint": source["registry_fingerprint"],
        "preflight_digest": proposal["preflight"]["digest"],
        "idempotency_key": proposal["idempotency_key"],
        "issued_at": proposal["issued_at"],
        "expires_at": proposal["expires_at"],
    }
    if any(row[field] != value for field, value in expected.items()):
        raise ValueError("operator command proposal column integrity check failed")


def _require_active_principal(
    conn: sqlite3.Connection, proposal: dict[str, Any]
) -> None:
    row = conn.execute(
        "SELECT 1 FROM principals WHERE id = ? AND tenant_id = ? AND principal_type = 'human' AND status = 'active'",
        (proposal["principal_id"], proposal["tenant_id"]),
    ).fetchone()
    if row is None:
        raise OperatorCommandConflictError(
            "principal_inactive", "The confirming human is no longer active."
        )


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
