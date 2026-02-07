from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json
from infrastructure.db.tenancy import ensure_client


def create_belief_revision(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    hypothesis_key: str,
    prior: float,
    likelihood: float,
    posterior: float,
    confidence: float,
    evidence_ref: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    revision_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO belief_revisions (
            id,
            client_id,
            brand_id,
            product_id,
            hypothesis_key,
            prior,
            likelihood,
            posterior,
            confidence,
            evidence_ref_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, json(?))
        """,
        (
            revision_id,
            client_id,
            brand_id,
            product_id,
            hypothesis_key,
            prior,
            likelihood,
            posterior,
            confidence,
            to_json(evidence_ref) or to_json({}),
        ),
    )
    conn.commit()
    return get_belief_revision(revision_id=revision_id) or {}


def get_belief_revision(*, revision_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM belief_revisions WHERE id = ?", (revision_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_belief_revisions(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    hypothesis_key: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    conn = get_connection()
    filters = ["client_id = ?"]
    params: list[Any] = [client_id]
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if product_id:
        filters.append("product_id = ?")
        params.append(product_id)
    if hypothesis_key:
        filters.append("hypothesis_key = ?")
        params.append(hypothesis_key)
    where = f"WHERE {' AND '.join(filters)}"
    rows = conn.execute(
        f"""
        SELECT * FROM belief_revisions
        {where}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def get_latest_belief_revision(
    *,
    client_id: str,
    brand_id: Optional[str] = None,
    product_id: Optional[str] = None,
    hypothesis_key: Optional[str] = None,
) -> Dict[str, Any] | None:
    revisions = list_belief_revisions(
        client_id=client_id,
        brand_id=brand_id,
        product_id=product_id,
        hypothesis_key=hypothesis_key,
        limit=1,
    )
    return revisions[0] if revisions else None


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "hypothesis_key": row["hypothesis_key"],
        "prior": row["prior"],
        "likelihood": row["likelihood"],
        "posterior": row["posterior"],
        "confidence": row["confidence"],
        "evidence_ref": from_json(row["evidence_ref_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_belief_revision",
    "get_belief_revision",
    "list_belief_revisions",
    "get_latest_belief_revision",
]

