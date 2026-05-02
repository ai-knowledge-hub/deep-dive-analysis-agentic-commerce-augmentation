from __future__ import annotations

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
            status,
        ),
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


__all__ = [
    "ensure_agent_registry_version",
    "get_agent_registry_version",
    "get_latest_agent_registry_version",
]
