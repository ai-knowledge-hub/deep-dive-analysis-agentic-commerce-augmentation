"""Backward compatibility: re-exports from infrastructure DB JSON helpers."""

from infrastructure.db.json import from_json, to_json

__all__ = ["from_json", "to_json"]
