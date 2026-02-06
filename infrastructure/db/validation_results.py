from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def create_result(
    *,
    job_id: str,
    provider: str,
    model: Optional[str],
    structured_result: Dict[str, Any],
    raw_response: Optional[str],
    score: Optional[float],
    winner_id: Optional[str],
    evidence_strength: Optional[str],
    latency_ms: Optional[int],
    cost_usd: Optional[float],
) -> Dict[str, Any]:
    result_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO validation_results (
            id,
            job_id,
            provider,
            model,
            structured_result_json,
            raw_response_text,
            score,
            winner_id,
            evidence_strength,
            latency_ms,
            cost_usd
        )
        VALUES (?, ?, ?, ?, json(?), ?, ?, ?, ?, ?, ?)
        """,
        (
            result_id,
            job_id,
            provider,
            model,
            to_json(structured_result) or to_json({}),
            raw_response,
            score,
            winner_id,
            evidence_strength,
            latency_ms,
            cost_usd,
        ),
    )
    conn.commit()
    return get_result(result_id) or {}


def get_result(result_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM validation_results WHERE id = ?", (result_id,))
        .fetchone()
    )
    return _row(row) if row else None


def get_latest_for_job(job_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute(
            """
            SELECT * FROM validation_results
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (job_id,),
        )
        .fetchone()
    )
    return _row(row) if row else None


def _row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "job_id": row["job_id"],
        "provider": row["provider"],
        "model": row["model"],
        "structured_result": from_json(row["structured_result_json"], default={}),
        "raw_response": row["raw_response_text"],
        "score": row["score"],
        "winner_id": row["winner_id"],
        "evidence_strength": row["evidence_strength"],
        "latency_ms": row["latency_ms"],
        "cost_usd": row["cost_usd"],
        "created_at": row["created_at"],
    }


__all__ = ["create_result", "get_result", "get_latest_for_job"]
