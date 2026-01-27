"""Backward compatibility: re-exports from infrastructure DB users."""

from infrastructure.db.users import ensure_user, get_user, update_metadata

__all__ = ["ensure_user", "get_user", "update_metadata"]
