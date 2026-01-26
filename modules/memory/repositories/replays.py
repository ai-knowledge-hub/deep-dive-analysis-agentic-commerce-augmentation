"""Replay record repository hooks (auditable run logs)."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional

from shared.db.connection import get_connection
from modules.memory.repositories.base import from_json, to_json
from modules.memory.repositories.clients import DEFAULT_CLIENT_ID, ensure_client
from modules.memory.repositories import users as users_repo


def _row_to_dict(row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "run_type": row["run_type"],
        "entity_type": row["entity_type"],
        "entity_id": row["entity_id"],
        "user_id": row["user_id"],
        "client_id": row["client_id"],
        "session_id": row["session_id"],
        "record": from_json(row["record_json"], default={}),
        "created_at": row["created_at"],
    }


def create_replay_record(
    *,
    run_type: str,
    record: Dict[str, Any],
    client_id: str = DEFAULT_CLIENT_ID,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    ensure_client(client_id)
    if user_id:
        users_repo.ensure_user(user_id)
    replay_id = str(uuid.uuid4())
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO replay_records (
            id, run_type, entity_type, entity_id, user_id, client_id, session_id, record_json
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            replay_id,
            run_type,
            entity_type,
            entity_id,
            user_id,
            client_id,
            session_id,
            to_json(record),
        ),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM replay_records WHERE id = ?", (replay_id,)
    ).fetchone()
    return _row_to_dict(row)


def list_replay_records(
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    run_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    ensure_client(client_id)
    where = ["client_id = ?"]
    params: List[Any] = [client_id]
    if user_id:
        where.append("user_id = ?")
        params.append(user_id)
    if session_id:
        where.append("session_id = ?")
        params.append(session_id)
    if entity_type:
        where.append("entity_type = ?")
        params.append(entity_type)
    if entity_id:
        where.append("entity_id = ?")
        params.append(entity_id)
    if run_type:
        where.append("run_type = ?")
        params.append(run_type)
    params.append(limit)
    rows = (
        get_connection()
        .execute(
            f"""
            SELECT * FROM replay_records
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC
            LIMIT ?
            """,
            tuple(params),
        )
        .fetchall()
    )
    return [_row_to_dict(row) for row in rows]


def get_replay_record(
    replay_id: str,
    *,
    client_id: str = DEFAULT_CLIENT_ID,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    ensure_client(client_id)
    row = (
        get_connection()
        .execute(
            """
        SELECT * FROM replay_records
        WHERE id = ? AND client_id = ?
        """,
            (replay_id, client_id),
        )
        .fetchone()
    )
    if not row:
        return None
    record = _row_to_dict(row)
    if user_id and record.get("user_id") and record.get("user_id") != user_id:
        return None
    return record


__all__ = ["create_replay_record", "list_replay_records", "get_replay_record"]
