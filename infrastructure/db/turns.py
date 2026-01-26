from __future__ import annotations

from typing import Any, Dict, List

from modules.memory.repositories import turns as _repo


def add_turn(
    *,
    session_id: str,
    speaker: str,
    content: str,
    metadata: dict | None = None,
) -> Dict[str, Any]:
    return _repo.add_turn(session_id, speaker, content, metadata=metadata)


def list_turns(*, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    return _repo.list_turns(session_id, limit=limit)


def list_recent_turns(*, session_id: str, limit: int = 1) -> List[Dict[str, Any]]:
    return _repo.list_recent_turns(session_id, limit=limit)


__all__ = ["add_turn", "list_turns", "list_recent_turns"]

