"""Backward compatibility: re-exports from infrastructure DB semantic memory."""

from infrastructure.db.semantic import DEFAULT_USER_ID, get_entry, list_entries, upsert_entry
from infrastructure.db.semantic import delete_entry  # type: ignore[attr-defined]

__all__ = [
    "DEFAULT_USER_ID",
    "delete_entry",
    "get_entry",
    "list_entries",
    "upsert_entry",
]
