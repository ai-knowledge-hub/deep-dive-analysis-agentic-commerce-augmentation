from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.memory.repositories import replays as _repo


def create_replay_record(
    *,
    run_type: str,
    record: Dict[str, Any],
    client_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
) -> Dict[str, Any]:
    return _repo.create_replay_record(
        run_type=run_type,
        record=record,
        client_id=client_id,
        user_id=user_id,
        session_id=session_id,
        entity_type=entity_type,
        entity_id=entity_id,
    )


def list_replay_records(
    *,
    client_id: str,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    run_type: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    return _repo.list_replay_records(
        client_id=client_id,
        user_id=user_id,
        session_id=session_id,
        entity_type=entity_type,
        entity_id=entity_id,
        run_type=run_type,
        limit=limit,
    )


def get_replay_record(
    replay_id: str,
    *,
    client_id: str,
    user_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    return _repo.get_replay_record(replay_id, client_id=client_id, user_id=user_id)


__all__ = ["create_replay_record", "list_replay_records", "get_replay_record"]

