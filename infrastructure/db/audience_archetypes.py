from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_archetype(
    *,
    client_id: str,
    label: str,
    brand_id: Optional[str] = None,
    domain_vertical: Optional[str] = None,
    description: Optional[str] = None,
    archetype: Optional[Dict[str, Any]] = None,
    source: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    archetype_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO audience_archetypes
            (id, client_id, brand_id, domain_vertical, label, description, archetype_json, source, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, json(?), ?, json(?))
        """,
        (
            archetype_id,
            client_id,
            brand_id,
            domain_vertical,
            label,
            description,
            to_json(archetype) or to_json({}),
            source,
            to_json(metadata) or to_json({}),
        ),
    )
    conn.commit()
    return get_archetype(archetype_id, client_id=client_id) or {}


def get_archetype(
    archetype_id: str, *, client_id: str | None = None
) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            "SELECT * FROM audience_archetypes WHERE id = ? AND client_id = ?",
            (archetype_id, client_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM audience_archetypes WHERE id = ?",
            (archetype_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def list_archetypes(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    domain_vertical: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    conditions = ["client_id = ?"]
    params: List[Any] = [client_id]
    if brand_id:
        conditions.append("brand_id = ?")
        params.append(brand_id)
    if domain_vertical:
        conditions.append("domain_vertical = ?")
        params.append(domain_vertical)
    where_clause = " AND ".join(conditions)
    params.append(limit)
    rows = conn.execute(
        f"""
        SELECT * FROM audience_archetypes
        WHERE {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    return [_row_to_dict(row) for row in rows]


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "domain_vertical": row["domain_vertical"],
        "label": row["label"],
        "description": row["description"],
        "archetype": from_json(row["archetype_json"]) or {},
        "source": row["source"],
        "metadata": from_json(row["metadata_json"]) or {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = ["create_archetype", "get_archetype", "list_archetypes"]
