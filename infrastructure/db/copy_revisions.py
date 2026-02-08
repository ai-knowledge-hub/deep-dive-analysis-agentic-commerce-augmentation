from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_revision(
    *,
    client_id: str,
    brand_id: Optional[str],
    product_id: str,
    source_type: str,
    source_id: Optional[str],
    source_variant_id: Optional[str],
    base_description: str,
    candidate_description: str,
    status: str = "draft",
    notes: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    created_by: Optional[str] = None,
) -> Dict[str, Any]:
    revision_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO copy_revisions (
            id,
            client_id,
            brand_id,
            product_id,
            source_type,
            source_id,
            source_variant_id,
            base_description,
            candidate_description,
            status,
            notes,
            metadata_json,
            created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, json(?), ?)
        """,
        (
            revision_id,
            client_id,
            brand_id,
            product_id,
            source_type,
            source_id,
            source_variant_id,
            base_description,
            candidate_description,
            status,
            notes,
            to_json(metadata) or to_json({}),
            created_by,
        ),
    )
    conn.commit()
    return get_revision(revision_id) or {}


def get_revision(revision_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM copy_revisions WHERE id = ?", (revision_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_revisions(
    *,
    client_id: str,
    product_id: Optional[str] = None,
    source_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    filters: list[str] = ["client_id = ?"]
    params: list[Any] = [client_id]
    if product_id:
        filters.append("product_id = ?")
        params.append(product_id)
    if source_type:
        filters.append("source_type = ?")
        params.append(source_type)
    if status:
        filters.append("status = ?")
        params.append(status)
    where_clause = " AND ".join(filters)
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT * FROM copy_revisions
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (*params, limit),
        )
        .fetchall()
    )
    return [_row(row) for row in rows]


def update_revision_status(
    *,
    revision_id: str,
    status: str,
    approved_by: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any] | None:
    updates = ["status = ?", "updated_at = datetime('now')"]
    params: list[Any] = [status]
    if approved_by is not None:
        updates.append("approved_by = ?")
        params.append(approved_by)
    if notes is not None:
        updates.append("notes = ?")
        params.append(notes)
    params.append(revision_id)
    conn = get_connection()
    conn.execute(
        f"""
        UPDATE copy_revisions
        SET {", ".join(updates)}
        WHERE id = ?
        """,
        params,
    )
    conn.commit()
    return get_revision(revision_id)


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "source_type": row["source_type"],
        "source_id": row["source_id"],
        "source_variant_id": row["source_variant_id"],
        "base_description": row["base_description"],
        "candidate_description": row["candidate_description"],
        "status": row["status"],
        "notes": row["notes"],
        "metadata": from_json(row["metadata_json"], default={}),
        "created_by": row["created_by"],
        "approved_by": row["approved_by"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_revision",
    "get_revision",
    "list_revisions",
    "update_revision_status",
]
