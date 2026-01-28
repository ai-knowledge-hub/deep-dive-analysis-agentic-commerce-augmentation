from __future__ import annotations

from typing import Any, Dict, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json

DEFAULT_PROFILE_ID = "ucp-platform"


def get_platform_profile(*, profile_id: str = DEFAULT_PROFILE_ID) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM platform_profiles WHERE id = ?", (profile_id,))
        .fetchone()
    )
    return _profile_row(row) if row else None


def upsert_platform_profile(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    name: str,
    version: str,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO platform_profiles (id, name, version, profile_json)
        VALUES (?, ?, ?, json(?))
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            version = excluded.version,
            profile_json = excluded.profile_json,
            updated_at = datetime('now')
        """,
        (profile_id, name, version, to_json(profile) or to_json({})),
    )
    conn.commit()
    return get_platform_profile(profile_id=profile_id) or {}


def ensure_platform_profile(
    *,
    profile_id: str = DEFAULT_PROFILE_ID,
    name: str,
    version: str,
    profile: Dict[str, Any],
) -> Dict[str, Any]:
    existing = get_platform_profile(profile_id=profile_id)
    if existing:
        return existing
    return upsert_platform_profile(
        profile_id=profile_id, name=name, version=version, profile=profile
    )


def _profile_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "name": row["name"],
        "version": row["version"],
        "profile": from_json(row["profile_json"], default={}),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "DEFAULT_PROFILE_ID",
    "get_platform_profile",
    "upsert_platform_profile",
    "ensure_platform_profile",
]
