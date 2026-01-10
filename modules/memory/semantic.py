"""Long-lived semantic memory backed by SQLite."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

from shared.db.connection import init_db, set_database_path
from modules.memory.repositories import semantic as semantic_repo


class SemanticMemory:
    """SQLite-backed semantic memory.

    Args:
        data_path: Optional path to a SQLite database file. Kept for
            backwards compatibility with the previous JSON signature.
        user_id: Which user the semantic memory belongs to. Defaults to a
            shared "__default__" user for demo mode.
    """

    def __init__(self, data_path: Path | None = None, user_id: str | None = None) -> None:
        if data_path:
            set_database_path(data_path)
        init_db()
        self._user_id = user_id or semantic_repo.DEFAULT_USER_ID

    def get(self, key: str) -> List[str]:
        """Get a list value from semantic memory."""
        entry = semantic_repo.get_entry(key, self._user_id)
        value = entry["value"] if entry else None
        if isinstance(value, list):
            return value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return list(value)
        return []

    def set(self, key: str, values: List[str]) -> None:
        """Set a list value in semantic memory."""
        semantic_repo.upsert_entry(key, list(values), user_id=self._user_id)

    def append(self, key: str, value: str) -> None:
        """Append a value to a list in semantic memory."""
        entries = self.get(key)
        entries.append(value)
        self.set(key, entries)


__all__ = ["SemanticMemory"]
