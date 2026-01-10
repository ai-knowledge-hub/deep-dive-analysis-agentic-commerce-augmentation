"""Shared helpers for SQLite repositories."""

from __future__ import annotations

import json
from typing import Any


def to_json(value: Any | None) -> str | None:
    """Serialize dictionaries/lists to JSON strings for storage."""
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False)


def from_json(value: str | None, default: Any | None = None) -> Any:
    """Deserialize JSON strings from SQLite."""
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


__all__ = ["to_json", "from_json"]
