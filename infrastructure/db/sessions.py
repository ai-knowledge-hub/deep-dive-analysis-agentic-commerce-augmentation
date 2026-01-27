from __future__ import annotations

from typing import Any, Dict, List, Optional

from modules.memory.repositories import sessions as _repo


def create_session(
    *,
    user_id: str | None = None,
    state: dict | None = None,
    client_id: str,
    brand_id: str | None = None,
) -> Dict[str, Any]:
    return _repo.create_session(
        user_id=user_id, state=state, client_id=client_id, brand_id=brand_id
    )


def get_session(*, session_id: str, client_id: str | None = None) -> Optional[Dict[str, Any]]:
    return _repo.get_session(session_id, client_id=client_id)


def update_state(*, session_id: str, state: dict) -> None:
    _repo.update_state(session_id, state)


def list_sessions(
    *,
    client_id: str,
    user_id: str | None = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    return _repo.list_sessions(user_id=user_id, limit=limit, client_id=client_id)


def delete_session(*, session_id: str) -> None:
    _repo.delete_session(session_id)


__all__ = [
    "create_session",
    "get_session",
    "update_state",
    "list_sessions",
    "delete_session",
]

