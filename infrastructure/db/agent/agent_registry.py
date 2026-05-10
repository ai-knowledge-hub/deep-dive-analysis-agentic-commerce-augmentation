from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def ensure_agent_registry_version(
    *,
    registry_version: str,
    registry_fingerprint: str,
    payload: Dict[str, Any],
    hash_algorithm: str = "sha256",
    source: str = "static_code",
    status: str = "active",
) -> Dict[str, Any]:
    conn = get_connection()
    release_status = status or "active"
    active_before = get_active_agent_registry_version()
    conn.execute(
        """
        INSERT OR IGNORE INTO agent_registry_versions (
            id,
            registry_version,
            registry_fingerprint,
            hash_algorithm,
            source,
            payload_json,
            status
        )
        VALUES (?, ?, ?, ?, ?, json(?), ?)
        """,
        (
            registry_fingerprint,
            registry_version,
            registry_fingerprint,
            hash_algorithm,
            source,
            to_json(payload) or to_json({}),
            release_status,
        ),
    )
    conn.execute(
        """
        UPDATE agent_registry_versions
        SET
            registry_version = ?,
            hash_algorithm = ?,
            source = ?,
            payload_json = json(?),
            status = ?
        WHERE registry_fingerprint = ?
        """,
        (
            registry_version,
            hash_algorithm,
            source,
            to_json(payload) or to_json({}),
            release_status,
            registry_fingerprint,
        ),
    )
    if (
        release_status == "active"
        and active_before
        and active_before["registry_fingerprint"] != registry_fingerprint
    ):
        conn.execute(
            """
            UPDATE agent_registry_versions
            SET status = 'retired'
            WHERE status = 'active' AND registry_fingerprint != ?
            """,
            (registry_fingerprint,),
        )
        _create_registry_transition_event(
            previous=active_before,
            registry_version=registry_version,
            registry_fingerprint=registry_fingerprint,
            payload=payload,
            source=source,
        )
    conn.commit()
    return get_agent_registry_version(registry_fingerprint=registry_fingerprint) or {}


def get_agent_registry_version(
    *, registry_fingerprint: str
) -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_versions
            WHERE registry_fingerprint = ?
            """,
            (registry_fingerprint,),
        )
        .fetchone()
    )
    return _row(row) if row else None


def get_agent_registry_release_detail(
    *, registry_fingerprint: str, audit_limit: int = 20
) -> Optional[Dict[str, Any]]:
    release = get_agent_registry_version(registry_fingerprint=registry_fingerprint)
    if not release:
        return None
    payload = release.get("payload") or {}
    return {
        **_release_payload_summary(release, payload),
        "payload": payload,
        "audit_events": list_agent_registry_audit_events(
            registry_fingerprint=registry_fingerprint,
            limit=audit_limit,
        ),
    }


def get_latest_agent_registry_version() -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_versions
            ORDER BY created_at DESC, registry_fingerprint ASC
            LIMIT 1
            """
        )
        .fetchone()
    )
    return _row(row) if row else None


def get_active_agent_registry_version() -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_versions
            WHERE status = 'active'
            ORDER BY created_at DESC, registry_fingerprint ASC
            LIMIT 1
            """
        )
        .fetchone()
    )
    return _row(row) if row else None


def list_agent_registry_versions(
    *, status: Optional[str] = None, limit: int = 20
) -> list[Dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_registry_versions
            {where_clause}
            ORDER BY
                CASE status WHEN 'active' THEN 0 ELSE 1 END,
                created_at DESC,
                registry_fingerprint ASC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        .fetchall()
    )
    return [_release_row(row) for row in rows]


def list_agent_registry_audit_events(
    *, registry_fingerprint: Optional[str] = None, limit: int = 50
) -> list[Dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if registry_fingerprint:
        filters.append("registry_fingerprint = ?")
        params.append(registry_fingerprint)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_registry_audit_events
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, int(limit)),
        )
        .fetchall()
    )
    return [_audit_row(row) for row in rows]


def ensure_agent_registry_tool_ownership(
    *, ownership: list[Dict[str, Any]], source: str = "registry_default"
) -> list[Dict[str, Any]]:
    conn = get_connection()
    for item in ownership:
        tool_id = str(item.get("tool_id") or "").strip()
        owner_principal_id = str(item.get("owner_principal_id") or "").strip()
        steward_team = str(item.get("steward_team") or "").strip()
        if not tool_id or not owner_principal_id or not steward_team:
            continue
        conn.execute(
            """
            INSERT INTO agent_registry_tool_ownership (
                tool_id,
                owner_principal_id,
                steward_team,
                source
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(tool_id) DO UPDATE SET
                owner_principal_id = agent_registry_tool_ownership.owner_principal_id,
                steward_team = agent_registry_tool_ownership.steward_team,
                source = agent_registry_tool_ownership.source,
                updated_at = agent_registry_tool_ownership.updated_at
            """,
            (tool_id, owner_principal_id, steward_team, source),
        )
    conn.commit()
    return list_agent_registry_tool_ownership()


def list_agent_registry_tool_ownership() -> list[Dict[str, Any]]:
    rows = (
        get_connection()
        .execute(
            """
            SELECT *
            FROM agent_registry_tool_ownership
            ORDER BY tool_id ASC
            """
        )
        .fetchall()
    )
    return [_ownership_row(row) for row in rows]


def ensure_agent_registry_harness_profiles(
    *, profiles: list[Dict[str, Any]], source: str = "registry_default"
) -> list[Dict[str, Any]]:
    conn = get_connection()
    for profile in profiles:
        profile_id = str(profile.get("id") or "").strip()
        name = str(profile.get("name") or "").strip()
        default_run_mode = str(profile.get("default_run_mode") or "").strip()
        default_policy_profile_id = str(
            profile.get("default_policy_profile_id") or ""
        ).strip()
        if not profile_id or not name or not default_run_mode or not default_policy_profile_id:
            continue
        conn.execute(
            """
            INSERT INTO agent_registry_harness_profiles (
                id,
                name,
                description,
                default_run_mode,
                default_policy_profile_id,
                allowed_run_modes_json,
                allowed_policy_profile_ids_json,
                planner_mode,
                retry_strategy,
                fallback_order_json,
                approval_strategy,
                memory_policy,
                stopping_conditions_json,
                source,
                status
            )
            VALUES (?, ?, ?, ?, ?, json(?), json(?), ?, ?, json(?), ?, ?, json(?), ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = agent_registry_harness_profiles.name,
                description = agent_registry_harness_profiles.description,
                default_run_mode = agent_registry_harness_profiles.default_run_mode,
                default_policy_profile_id = agent_registry_harness_profiles.default_policy_profile_id,
                allowed_run_modes_json = agent_registry_harness_profiles.allowed_run_modes_json,
                allowed_policy_profile_ids_json = agent_registry_harness_profiles.allowed_policy_profile_ids_json,
                planner_mode = agent_registry_harness_profiles.planner_mode,
                retry_strategy = agent_registry_harness_profiles.retry_strategy,
                fallback_order_json = agent_registry_harness_profiles.fallback_order_json,
                approval_strategy = agent_registry_harness_profiles.approval_strategy,
                memory_policy = agent_registry_harness_profiles.memory_policy,
                stopping_conditions_json = agent_registry_harness_profiles.stopping_conditions_json,
                source = agent_registry_harness_profiles.source,
                status = agent_registry_harness_profiles.status,
                updated_at = agent_registry_harness_profiles.updated_at
            """,
            (
                profile_id,
                name,
                str(profile.get("description") or ""),
                default_run_mode,
                default_policy_profile_id,
                to_json(profile.get("allowed_run_modes") or []) or "[]",
                to_json(profile.get("allowed_policy_profile_ids") or []) or "[]",
                profile.get("planner_mode"),
                profile.get("retry_strategy"),
                to_json(profile.get("fallback_order") or []) or "[]",
                profile.get("approval_strategy"),
                profile.get("memory_policy"),
                to_json(profile.get("stopping_conditions") or []) or "[]",
                source,
                str(profile.get("status") or "active"),
            ),
        )
    conn.commit()
    return list_agent_registry_harness_profiles()


def list_agent_registry_harness_profiles(
    *, status: Optional[str] = "active"
) -> list[Dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if status:
        filters.append("status = ?")
        params.append(status)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_registry_harness_profiles
            {where_clause}
            ORDER BY id ASC
            """,
            tuple(params),
        )
        .fetchall()
    )
    return [_harness_profile_row(row) for row in rows]


def update_agent_registry_harness_profile(
    *, profile_id: str, profile: Dict[str, Any], source: str = "operator_override"
) -> Dict[str, Any]:
    normalized_id = str(profile_id or profile.get("id") or "").strip()
    if not normalized_id:
        return {}
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_registry_harness_profiles (
            id,
            name,
            description,
            default_run_mode,
            default_policy_profile_id,
            allowed_run_modes_json,
            allowed_policy_profile_ids_json,
            planner_mode,
            retry_strategy,
            fallback_order_json,
            approval_strategy,
            memory_policy,
            stopping_conditions_json,
            source,
            status
        )
        VALUES (?, ?, ?, ?, ?, json(?), json(?), ?, ?, json(?), ?, ?, json(?), ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            description = excluded.description,
            default_run_mode = excluded.default_run_mode,
            default_policy_profile_id = excluded.default_policy_profile_id,
            allowed_run_modes_json = excluded.allowed_run_modes_json,
            allowed_policy_profile_ids_json = excluded.allowed_policy_profile_ids_json,
            planner_mode = excluded.planner_mode,
            retry_strategy = excluded.retry_strategy,
            fallback_order_json = excluded.fallback_order_json,
            approval_strategy = excluded.approval_strategy,
            memory_policy = excluded.memory_policy,
            stopping_conditions_json = excluded.stopping_conditions_json,
            source = excluded.source,
            status = excluded.status,
            updated_at = datetime('now')
        """,
        (
            normalized_id,
            str(profile.get("name") or normalized_id),
            str(profile.get("description") or ""),
            str(profile.get("default_run_mode") or "plan_only"),
            str(profile.get("default_policy_profile_id") or "human_approval_required"),
            to_json(profile.get("allowed_run_modes") or []) or "[]",
            to_json(profile.get("allowed_policy_profile_ids") or []) or "[]",
            profile.get("planner_mode"),
            profile.get("retry_strategy"),
            to_json(profile.get("fallback_order") or []) or "[]",
            profile.get("approval_strategy"),
            profile.get("memory_policy"),
            to_json(profile.get("stopping_conditions") or []) or "[]",
            source,
            str(profile.get("status") or "active"),
        ),
    )
    conn.commit()
    row = (
        conn.execute(
            "SELECT * FROM agent_registry_harness_profiles WHERE id = ?",
            (normalized_id,),
        ).fetchone()
    )
    return _harness_profile_row(row) if row else {}


def update_agent_registry_tool_ownership(
    *,
    tool_id: str,
    owner_principal_id: str,
    steward_team: str,
    source: str = "operator_override",
) -> Dict[str, Any]:
    normalized_tool_id = str(tool_id or "").strip()
    normalized_owner = str(owner_principal_id or "").strip()
    normalized_steward = str(steward_team or "").strip()
    if not normalized_tool_id or not normalized_owner or not normalized_steward:
        return {}
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_registry_tool_ownership (
            tool_id,
            owner_principal_id,
            steward_team,
            source
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tool_id) DO UPDATE SET
            owner_principal_id = excluded.owner_principal_id,
            steward_team = excluded.steward_team,
            source = excluded.source,
            updated_at = datetime('now')
        """,
        (normalized_tool_id, normalized_owner, normalized_steward, source),
    )
    conn.commit()
    row = (
        conn.execute(
            """
            SELECT *
            FROM agent_registry_tool_ownership
            WHERE tool_id = ?
            """,
            (normalized_tool_id,),
        ).fetchone()
    )
    return _ownership_row(row) if row else {}


def create_agent_registry_audit_event(
    *,
    event_type: str,
    registry_fingerprint: str,
    registry_version: str,
    diff: Dict[str, Any],
    previous_registry_fingerprint: Optional[str] = None,
    source: str = "system",
) -> Dict[str, Any]:
    event_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO agent_registry_audit_events (
            id,
            event_type,
            previous_registry_fingerprint,
            registry_fingerprint,
            registry_version,
            source,
            diff_json
        )
        VALUES (?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            event_id,
            event_type,
            previous_registry_fingerprint,
            registry_fingerprint,
            registry_version,
            source,
            to_json(diff) or to_json({}),
        ),
    )
    conn.commit()
    row = (
        conn.execute(
            "SELECT * FROM agent_registry_audit_events WHERE id = ?",
            (event_id,),
        ).fetchone()
    )
    return _audit_row(row) if row else {}


def _create_registry_transition_event(
    *,
    previous: Dict[str, Any],
    registry_version: str,
    registry_fingerprint: str,
    payload: Dict[str, Any],
    source: str,
) -> None:
    get_connection().execute(
        """
        INSERT OR IGNORE INTO agent_registry_audit_events (
            id,
            event_type,
            previous_registry_fingerprint,
            registry_fingerprint,
            registry_version,
            source,
            diff_json
        )
        VALUES (?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            str(uuid.uuid4()),
            "registry_changed",
            previous["registry_fingerprint"],
            registry_fingerprint,
            registry_version,
            source,
            to_json(_diff_registry_payload(previous.get("payload") or {}, payload))
            or to_json({}),
        ),
    )


def _diff_registry_payload(
    previous: Dict[str, Any], current: Dict[str, Any]
) -> Dict[str, Any]:
    diff: Dict[str, Any] = {}
    for key in ("skills", "tools", "capabilities", "policy_profiles", "harness_profiles"):
        previous_items = _items_by_identity(previous.get(key))
        current_items = _items_by_identity(current.get(key))
        previous_ids = set(previous_items)
        current_ids = set(current_items)
        changed = sorted(
            item_id
            for item_id in previous_ids & current_ids
            if _canonical(previous_items[item_id]) != _canonical(current_items[item_id])
        )
        diff[key] = {
            "added": sorted(current_ids - previous_ids),
            "removed": sorted(previous_ids - current_ids),
            "changed": changed,
        }
    diff["skill_ids_by_tool_changed"] = _canonical(
        previous.get("skill_ids_by_tool") or {}
    ) != _canonical(current.get("skill_ids_by_tool") or {})
    return diff


def _items_by_identity(value: Any) -> Dict[str, Any]:
    if not isinstance(value, list):
        return {}
    items: Dict[str, Any] = {}
    for item in value:
        if not isinstance(item, dict):
            continue
        identity = item.get("id") or item.get("name")
        if identity:
            items[str(identity)] = item
    return items


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "registry_version": row["registry_version"],
        "registry_fingerprint": row["registry_fingerprint"],
        "hash_algorithm": row["hash_algorithm"],
        "source": row["source"],
        "payload": from_json(row["payload_json"], {}),
        "status": row["status"],
        "created_at": row["created_at"],
    }


def _audit_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "event_type": row["event_type"],
        "previous_registry_fingerprint": row["previous_registry_fingerprint"],
        "registry_fingerprint": row["registry_fingerprint"],
        "registry_version": row["registry_version"],
        "source": row["source"],
        "diff": from_json(row["diff_json"], {}),
        "created_at": row["created_at"],
    }


def _release_row(row) -> Dict[str, Any]:
    payload = from_json(row["payload_json"], {})
    return _release_payload_summary(_row(row), payload)


def _release_payload_summary(
    release: Dict[str, Any], payload: Dict[str, Any]
) -> Dict[str, Any]:
    return {
        "id": release["id"],
        "registry_version": release["registry_version"],
        "registry_fingerprint": release["registry_fingerprint"],
        "hash_algorithm": release["hash_algorithm"],
        "source": release["source"],
        "status": release["status"],
        "created_at": release["created_at"],
        "counts": {
            "skills": len(payload.get("skills") or []),
            "tools": len(payload.get("tools") or []),
            "capabilities": len(payload.get("capabilities") or []),
            "policy_profiles": len(payload.get("policy_profiles") or []),
            "harness_profiles": len(payload.get("harness_profiles") or []),
        },
    }


def _ownership_row(row) -> Dict[str, Any]:
    return {
        "tool_id": row["tool_id"],
        "owner_principal_id": row["owner_principal_id"],
        "steward_team": row["steward_team"],
        "source": row["source"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _harness_profile_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "default_run_mode": row["default_run_mode"],
        "default_policy_profile_id": row["default_policy_profile_id"],
        "allowed_run_modes": from_json(row["allowed_run_modes_json"], []),
        "allowed_policy_profile_ids": from_json(
            row["allowed_policy_profile_ids_json"], []
        ),
        "planner_mode": row["planner_mode"],
        "retry_strategy": row["retry_strategy"],
        "fallback_order": from_json(row["fallback_order_json"], []),
        "approval_strategy": row["approval_strategy"],
        "memory_policy": row["memory_policy"],
        "stopping_conditions": from_json(row["stopping_conditions_json"], []),
        "source": row["source"],
        "status": row["status"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_agent_registry_audit_event",
    "ensure_agent_registry_harness_profiles",
    "ensure_agent_registry_tool_ownership",
    "ensure_agent_registry_version",
    "get_active_agent_registry_version",
    "get_agent_registry_release_detail",
    "get_agent_registry_version",
    "get_latest_agent_registry_version",
    "list_agent_registry_audit_events",
    "list_agent_registry_harness_profiles",
    "list_agent_registry_tool_ownership",
    "list_agent_registry_versions",
    "update_agent_registry_harness_profile",
    "update_agent_registry_tool_ownership",
]
