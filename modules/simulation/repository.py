"""SQLite persistence for simulation runs."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json
from modules.memory.repositories.clients import DEFAULT_CLIENT_ID, ensure_client


def create_run(
    *,
    query: str,
    scenario: dict,
    products: list,
    result: dict,
    user_id: str | None = None,
    session_id: str | None = None,
    client_id: str = DEFAULT_CLIENT_ID,
    brand_id: str | None = None,
    product_id: str | None = None,
) -> Dict[str, Any]:
    run_id = str(uuid.uuid4())
    conn = get_connection()
    ensure_client(client_id)
    conn.execute(
        """
        INSERT INTO simulation_runs
            (id, user_id, session_id, client_id, brand_id, product_id, query, scenario_json, products_json, result_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            user_id,
            session_id,
            client_id,
            brand_id,
            product_id,
            query,
            to_json(scenario),
            to_json(products),
            to_json(result),
        ),
    )
    conn.commit()
    _store_lessons(run_id, user_id, client_id, (result.get("lessons") or []))
    return get_run(run_id) or {}


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    row = (
        get_connection()
        .execute("SELECT * FROM simulation_runs WHERE id = ?", (run_id,))
        .fetchone()
    )
    if not row:
        return None
    return _row_to_dict(row)


def list_runs(
    user_id: str | None = None,
    limit: int = 20,
    client_id: str = DEFAULT_CLIENT_ID,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    if user_id:
        rows = conn.execute(
            """
            SELECT * FROM simulation_runs
            WHERE user_id = ? AND client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, client_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM simulation_runs
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def update_retest(run_id: str, retest: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE simulation_runs SET retest_json = ? WHERE id = ?",
        (to_json(retest), run_id),
    )
    conn.commit()


def update_scenario(run_id: str, scenario: dict) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE simulation_runs SET scenario_json = ? WHERE id = ?",
        (to_json(scenario), run_id),
    )
    conn.commit()


def list_lessons(
    user_id: str | None = None,
    limit: int = 50,
    client_id: str = DEFAULT_CLIENT_ID,
) -> List[Dict[str, Any]]:
    conn = get_connection()
    if user_id:
        rows = conn.execute(
            """
            SELECT * FROM simulation_lessons
            WHERE user_id = ? AND client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, client_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """
            SELECT * FROM simulation_lessons
            WHERE client_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (client_id, limit),
        ).fetchall()
    return [
        {
            "id": row["id"],
            "run_id": row["run_id"],
            "user_id": row["user_id"],
            "client_id": row["client_id"],
            "lesson": row["lesson"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "session_id": row["session_id"],
        "client_id": row["client_id"],
        "brand_id": row["brand_id"],
        "product_id": row["product_id"],
        "query": row["query"],
        "scenario": from_json(row["scenario_json"], default={}),
        "products": from_json(row["products_json"], default=[]),
        "result": from_json(row["result_json"], default={}),
        "retest": from_json(row["retest_json"], default=None),
        "created_at": row["created_at"],
    }


def _store_lessons(
    run_id: str,
    user_id: str | None,
    client_id: str,
    lessons: list,
) -> None:
    if not lessons:
        return
    conn = get_connection()
    conn.executemany(
        "INSERT INTO simulation_lessons (run_id, user_id, client_id, lesson) VALUES (?, ?, ?, ?)",
        [(run_id, user_id, client_id, lesson) for lesson in lessons],
    )
    conn.commit()


__all__ = [
    "create_run",
    "get_run",
    "list_runs",
    "update_retest",
    "update_scenario",
    "list_lessons",
]
