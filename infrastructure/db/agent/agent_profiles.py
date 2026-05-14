from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def ensure_agent_profiles(
    *, profiles: list[Dict[str, Any]], tenant_id: Optional[str] = None
) -> list[Dict[str, Any]]:
    conn = get_connection()
    for profile in profiles:
        profile_id = str(profile.get("id") or "").strip()
        principal_id = str(profile.get("principal_id") or profile_id).strip()
        principal_type = str(profile.get("principal_type") or "external_agent").strip()
        name = str(profile.get("name") or profile_id).strip()
        if not profile_id or not principal_id or not name:
            continue
        conn.execute(
            """
            INSERT INTO principals (
                id,
                principal_type,
                tenant_id,
                display_name,
                metadata_json
            )
            VALUES (?, ?, ?, ?, json(?))
            ON CONFLICT(id) DO UPDATE SET
                tenant_id = COALESCE(excluded.tenant_id, principals.tenant_id),
                display_name = COALESCE(excluded.display_name, principals.display_name),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                principal_id,
                principal_type,
                tenant_id,
                name,
                to_json({"seeded_by": "agent_profile_defaults"}) or "{}",
            ),
        )
        metadata = {
            **dict(profile.get("metadata") or {}),
            "source": profile.get("source") or "registry_default",
        }
        conn.execute(
            """
            INSERT INTO agent_profiles (
                id,
                principal_id,
                tenant_id,
                name,
                default_harness_id,
                default_policy_profile_id,
                risk_tier,
                channel_type,
                metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, json(?))
            ON CONFLICT(id) DO UPDATE SET
                principal_id = agent_profiles.principal_id,
                tenant_id = agent_profiles.tenant_id,
                name = agent_profiles.name,
                default_harness_id = agent_profiles.default_harness_id,
                default_policy_profile_id = agent_profiles.default_policy_profile_id,
                risk_tier = agent_profiles.risk_tier,
                channel_type = agent_profiles.channel_type,
                metadata_json = agent_profiles.metadata_json,
                updated_at = agent_profiles.updated_at
            """,
            (
                profile_id,
                principal_id,
                tenant_id,
                name,
                profile.get("default_harness_id"),
                profile.get("default_policy_profile_id"),
                profile.get("risk_tier"),
                profile.get("channel_type"),
                to_json(metadata) or "{}",
            ),
        )
    conn.commit()
    return list_agent_profiles(tenant_id=tenant_id)


def get_agent_profile(
    *, profile_id: str, tenant_id: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    normalized_id = str(profile_id or "").strip()
    if not normalized_id:
        return None
    filters = ["id = ?"]
    params: list[Any] = [normalized_id]
    if tenant_id:
        filters.append("(tenant_id = ? OR tenant_id IS NULL)")
        params.append(tenant_id)
    row = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_profiles
            WHERE {" AND ".join(filters)}
            ORDER BY
                CASE WHEN tenant_id = ? THEN 0 ELSE 1 END,
                updated_at DESC
            LIMIT 1
            """,
            (*params, tenant_id or ""),
        )
        .fetchone()
    )
    return _agent_profile_row(row) if row else None


def list_agent_profiles(*, tenant_id: Optional[str] = None) -> list[Dict[str, Any]]:
    filters: list[str] = []
    params: list[Any] = []
    if tenant_id:
        filters.append("(tenant_id = ? OR tenant_id IS NULL)")
        params.append(tenant_id)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT *
            FROM agent_profiles
            {where_clause}
            ORDER BY id ASC
            """,
            tuple(params),
        )
        .fetchall()
    )
    return [_agent_profile_row(row) for row in rows]


def update_agent_profile_defaults(
    *,
    profile_id: str,
    principal_id: str,
    principal_type: str,
    name: str,
    tenant_id: Optional[str] = None,
    default_harness_id: Optional[str] = None,
    default_policy_profile_id: Optional[str] = None,
    risk_tier: Optional[str] = None,
    channel_type: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO principals (
            id,
            principal_type,
            tenant_id,
            display_name,
            metadata_json
        )
        VALUES (?, ?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            principal_type = excluded.principal_type,
            tenant_id = COALESCE(excluded.tenant_id, principals.tenant_id),
            display_name = excluded.display_name,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            principal_id,
            principal_type,
            tenant_id,
            name,
            to_json({"source": "operator_override"}) or "{}",
        ),
    )
    conn.execute(
        """
        INSERT INTO agent_profiles (
            id,
            principal_id,
            tenant_id,
            name,
            default_harness_id,
            default_policy_profile_id,
            risk_tier,
            channel_type,
            metadata_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            principal_id = excluded.principal_id,
            tenant_id = excluded.tenant_id,
            name = excluded.name,
            default_harness_id = excluded.default_harness_id,
            default_policy_profile_id = excluded.default_policy_profile_id,
            risk_tier = excluded.risk_tier,
            channel_type = excluded.channel_type,
            metadata_json = excluded.metadata_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            profile_id,
            principal_id,
            tenant_id,
            name,
            default_harness_id,
            default_policy_profile_id,
            risk_tier,
            channel_type,
            to_json({"source": "operator_override", **dict(metadata or {})}) or "{}",
        ),
    )
    conn.commit()
    return get_agent_profile(profile_id=profile_id, tenant_id=tenant_id) or {}


def _agent_profile_row(row) -> Dict[str, Any]:
    metadata = from_json(row["metadata_json"], {})
    return {
        "id": row["id"],
        "principal_id": row["principal_id"],
        "tenant_id": row["tenant_id"],
        "name": row["name"],
        "default_harness_id": row["default_harness_id"],
        "default_policy_profile_id": row["default_policy_profile_id"],
        "risk_tier": row["risk_tier"],
        "channel_type": row["channel_type"],
        "metadata": metadata,
        "source": metadata.get("source") or "persistent",
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "ensure_agent_profiles",
    "get_agent_profile",
    "list_agent_profiles",
    "update_agent_profile_defaults",
]
