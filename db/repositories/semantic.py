"""Backward compatibility: re-exports from modules.memory.repositories.semantic."""

from modules.memory.repositories.semantic import (
    DEFAULT_USER_ID,
    delete_entry,
    get_entry,
    list_entries,
    upsert_entry,
)

__all__ = ["DEFAULT_USER_ID", "delete_entry", "get_entry", "list_entries", "upsert_entry"]
