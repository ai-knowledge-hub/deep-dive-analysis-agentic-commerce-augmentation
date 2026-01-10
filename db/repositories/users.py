"""Backward compatibility: re-exports from modules.memory.repositories.users."""

from modules.memory.repositories.users import ensure_user, get_user, update_metadata

__all__ = ["ensure_user", "get_user", "update_metadata"]
