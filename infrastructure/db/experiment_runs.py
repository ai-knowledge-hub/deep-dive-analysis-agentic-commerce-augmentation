from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from infrastructure.db.connection import get_connection
from infrastructure.db.json import from_json, to_json


def create_run(
    *,
    experiment_id: str,
    variant_id: str,
    query_id: str,
    simulation_run_id: Optional[str] = None,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_runs
            (id, experiment_id, variant_id, query_id, simulation_run_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (run_id, experiment_id, variant_id, query_id, simulation_run_id),
    )
    conn.commit()
    return get_run(run_id) or {}


def list_runs(
    *,
    experiment_id: str,
    variant_id: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    if variant_id:
        rows = conn.execute(
            """
            SELECT * FROM experiment_runs
            WHERE experiment_id = ? AND variant_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (experiment_id, variant_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM experiment_runs
            WHERE experiment_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (experiment_id, limit),
        ).fetchall()
    return [_run_row(row) for row in rows]


def get_run(run_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM experiment_runs WHERE id = ?", (run_id,))
        .fetchone()
    )
    return _run_row(row) if row else None


def create_metric(
    *,
    experiment_id: str,
    variant_id: Optional[str],
    metrics: Dict[str, Any],
) -> Dict[str, Any]:
    metric_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO experiment_metrics
            (id, experiment_id, variant_id, metrics_json)
        VALUES (?, ?, ?, json(?))
        """,
        (metric_id, experiment_id, variant_id, to_json(metrics) or to_json({})),
    )
    conn.commit()
    return get_metric(metric_id) or {}


def get_metric(metric_id: str) -> Dict[str, Any] | None:
    row = (
        get_connection()
        .execute("SELECT * FROM experiment_metrics WHERE id = ?", (metric_id,))
        .fetchone()
    )
    return _metric_row(row) if row else None


def list_metrics(
    *,
    experiment_id: str,
    variant_id: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    if variant_id:
        rows = conn.execute(
            """
            SELECT * FROM experiment_metrics
            WHERE experiment_id = ? AND variant_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (experiment_id, variant_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM experiment_metrics
            WHERE experiment_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (experiment_id, limit),
        ).fetchall()
    return [_metric_row(row) for row in rows]


def delete_runs_for_experiment(experiment_id: str) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM experiment_runs WHERE experiment_id = ?",
        (experiment_id,),
    )
    conn.commit()
    return result.rowcount if result else 0


def delete_metrics_for_experiment(experiment_id: str) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM experiment_metrics WHERE experiment_id = ?",
        (experiment_id,),
    )
    conn.commit()
    return result.rowcount if result else 0


def delete_runs_for_simulation_run(simulation_run_id: str) -> int:
    conn = get_connection()
    result = conn.execute(
        "DELETE FROM experiment_runs WHERE simulation_run_id = ?",
        (simulation_run_id,),
    )
    conn.commit()
    return result.rowcount if result else 0


def _run_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "variant_id": row["variant_id"],
        "query_id": row["query_id"],
        "simulation_run_id": row["simulation_run_id"],
        "created_at": row["created_at"],
    }


def _metric_row(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "experiment_id": row["experiment_id"],
        "variant_id": row["variant_id"],
        "metrics": from_json(row["metrics_json"], default={}),
        "created_at": row["created_at"],
    }


__all__ = [
    "create_run",
    "list_runs",
    "get_run",
    "create_metric",
    "list_metrics",
    "get_metric",
    "delete_runs_for_experiment",
    "delete_metrics_for_experiment",
    "delete_runs_for_simulation_run",
]
