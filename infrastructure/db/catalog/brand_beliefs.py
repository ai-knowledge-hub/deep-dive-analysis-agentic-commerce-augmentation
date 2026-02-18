from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json
from infrastructure.db.core.tenancy import ensure_client


def create_belief(
    *,
    client_id: str,
    brand_id: str,
    product_id: Optional[str] = None,
    hypothesis: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    recommendation: Optional[str] = None,
    confidence: Optional[float] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    belief_id = str(uuid.uuid4())
    ensure_client(client_id)
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO brand_beliefs
            (id, client_id, brand_id, product_id, hypothesis_json, evidence_json, recommendation, confidence, metadata_json)
        VALUES (?, ?, ?, ?, json(?), json(?), ?, ?, json(?))
        """,
        (
            belief_id,
            client_id,
            brand_id,
            product_id,
            to_json(hypothesis) or to_json({}),
            to_json(evidence) or to_json({}),
            recommendation,
            confidence,
            to_json(metadata) or to_json({}),
        ),
    )
    conn.commit()
    return get_belief(belief_id, client_id=client_id) or {}


def get_belief(belief_id: str, *, client_id: str | None = None) -> Dict[str, Any] | None:
    conn = get_connection()
    if client_id:
        row = conn.execute(
            "SELECT * FROM brand_beliefs WHERE id = ? AND client_id = ?",
            (belief_id, client_id),
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT * FROM brand_beliefs WHERE id = ?",
            (belief_id,),
        ).fetchone()
    return _belief_row(row) if row else None


def list_beliefs(
    *,
    client_id: str,
    brand_id: str,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT * FROM brand_beliefs
        WHERE client_id = ? AND brand_id = ?
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (client_id, brand_id, limit),
    ).fetchall()
    return [_belief_row(row) for row in rows]


def latest_belief(
    *,
    client_id: str,
    brand_id: str,
) -> Dict[str, Any] | None:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT * FROM brand_beliefs
        WHERE client_id = ? AND brand_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (client_id, brand_id),
    ).fetchone()
    return _belief_row(row) if row else None


def _belief_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "hypothesis": from_json(row["hypothesis_json"]) or {},
        "evidence": from_json(row["evidence_json"]) or {},
        "recommendation": row["recommendation"],
        "confidence": row["confidence"],
        "metadata": from_json(row["metadata_json"]) or {},
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


__all__ = [
    "create_belief",
    "get_belief",
    "list_beliefs",
    "latest_belief",
]
