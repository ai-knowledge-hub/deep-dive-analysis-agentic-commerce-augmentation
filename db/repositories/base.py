"""Backward compatibility: re-exports from modules.memory.repositories.base."""

from modules.memory.repositories.base import from_json, to_json

__all__ = ["from_json", "to_json"]
