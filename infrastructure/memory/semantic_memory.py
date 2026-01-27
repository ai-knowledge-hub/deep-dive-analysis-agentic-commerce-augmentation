"""Infrastructure semantic memory adapter."""

from __future__ import annotations

from pathlib import Path
from typing import List, Sequence

from infrastructure.db.connection import init_db, set_database_path
from infrastructure.db import semantic as semantic_store


class SemanticMemory:
    """SQLite-backed semantic memory (tenant-aware)."""

    def __init__(
        self,
        data_path: Path | None = None,
        user_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        if data_path:
            set_database_path(data_path)
        init_db()
        self._user_id = user_id or semantic_store.DEFAULT_USER_ID
        self._client_id = client_id or semantic_store.DEFAULT_CLIENT_ID

    def get(self, key: str) -> List[str]:
        entry = semantic_store.get_entry(
            key=key, user_id=self._user_id, client_id=self._client_id
        )
        value = entry["value"] if entry else None
        if isinstance(value, list):
            return value
        if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            return list(value)
        return []

    def set(self, key: str, values: List[str]) -> None:
        semantic_store.upsert_entry(
            key=key,
            value=list(values),
            user_id=self._user_id,
            client_id=self._client_id,
        )

    def append(self, key: str, value: str) -> None:
        entries = self.get(key)
        entries.append(value)
        self.set(key, entries)


__all__ = ["SemanticMemory"]
