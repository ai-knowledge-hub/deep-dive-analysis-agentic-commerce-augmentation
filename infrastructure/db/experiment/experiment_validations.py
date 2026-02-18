from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.json import from_json, to_json


def create_validation(
    *,
    experiment_id: str,
    variant_id: Optional[str],
    client_id: str,
    brand_id: Optional[str],
    product_id: Optional[str],
    platform: Optional[str],
    query_text: Optional[str],
    observed_products: Optional[List[str]],
    observed_winner_variant_id: Optional[str],
    observed_position: Optional[int],
    notes: Optional[str],
    is_correct: Optional[bool],
    created_at: Optional[str] = None,
) -> Dict[str, Any]:
    validation_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_validations (
            id,
            experiment_id,
            variant_id,
            client_id,
            brand_id,
            product_id,
            platform,
            query_text,
            observed_products_json,
            observed_winner_variant_id,
            observed_position,
            notes,
            is_correct,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, json(?), ?, ?, ?, ?, COALESCE(?, datetime('now')))
        """,
        (
            validation_id,
            experiment_id,
            variant_id,
            client_id,
            brand_id,
            product_id,
            platform,
            query_text,
            to_json(observed_products or []),
            observed_winner_variant_id,
            observed_position,
            notes,
            1 if is_correct is True else 0 if is_correct is False else None,
            created_at,
        ),
    )
    conn.commit()
    return get_validation(validation_id) or {}


def get_validation(validation_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM experiment_validations WHERE id = ?", (validation_id,))
        .fetchone()
    )
    return _row(row) if row else None


def list_validations(
    *,
    experiment_id: Optional[str] = None,
    brand_id: Optional[str] = None,
    client_id: Optional[str] = None,
    limit: int = 100,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    filters: list[str] = []
    params: list[Any] = []
    if experiment_id:
        filters.append("experiment_id = ?")
        params.append(experiment_id)
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if client_id:
        filters.append("client_id = ?")
        params.append(client_id)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    rows = conn.execute(
        f"""
        SELECT * FROM experiment_validations
        {where_clause}
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return [_row(row) for row in rows]


def count_validations(
    *, experiment_id: Optional[str] = None, brand_id: Optional[str] = None, client_id: Optional[str] = None
) -> int:
    conn = get_connection()
    filters: list[str] = []
    params: list[Any] = []
    if experiment_id:
        filters.append("experiment_id = ?")
        params.append(experiment_id)
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if client_id:
        filters.append("client_id = ?")
        params.append(client_id)
    where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
    row = conn.execute(
        f"SELECT COUNT(*) as count FROM experiment_validations {where_clause}",
        params,
    ).fetchone()
    return int(row["count"]) if row else 0


def accuracy_summary(
    *, experiment_id: Optional[str] = None, brand_id: Optional[str] = None, client_id: Optional[str] = None
) -> Dict[str, Any]:
    conn = get_connection()
    filters: list[str] = ["is_correct IS NOT NULL"]
    params: list[Any] = []
    if experiment_id:
        filters.append("experiment_id = ?")
        params.append(experiment_id)
    if brand_id:
        filters.append("brand_id = ?")
        params.append(brand_id)
    if client_id:
        filters.append("client_id = ?")
        params.append(client_id)
    where_clause = f"WHERE {' AND '.join(filters)}"
    row = conn.execute(
        f"""
        SELECT
            COUNT(*) as verified_runs,
            SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_runs
        FROM experiment_validations
        {where_clause}
        """,
        params,
    ).fetchone()
    verified_runs = int(row["verified_runs"] or 0) if row else 0
    correct_runs = int(row["correct_runs"] or 0) if row else 0
    accuracy = (correct_runs / verified_runs) if verified_runs else 0.0
    return {
        "verified_runs": verified_runs,
        "correct_runs": correct_runs,
        "accuracy": accuracy,
    }


def delete_validations_for_experiment(experiment_id: str) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM experiment_validations WHERE experiment_id = ?",
        (experiment_id,),
    )
    conn.commit()
    return result.rowcount if result else 0


def _row(row) -> Dict[str, Any]:
    is_correct = row["is_correct"]
    if is_correct is not None:
        is_correct = bool(is_correct)
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "variant_id": row["variant_id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "platform": row["platform"],
        "query_text": row["query_text"],
        "observed_products": from_json(row["observed_products_json"], default=[]),
        "observed_winner_variant_id": row["observed_winner_variant_id"],
        "observed_position": row["observed_position"],
        "notes": row["notes"],
        "is_correct": is_correct,
        "created_at": row["created_at"],
    }


__all__ = [
    "create_validation",
    "get_validation",
    "list_validations",
    "count_validations",
    "accuracy_summary",
    "delete_validations_for_experiment",
]
