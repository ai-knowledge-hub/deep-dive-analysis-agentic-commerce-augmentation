"""Infrastructure wrapper for DB bootstrap helpers.

Canonical implementation currently lives in `shared.db.connection`.
This module exists to keep application code from depending on `shared/*` directly.
"""

from __future__ import annotations

from pathlib import Path

from shared.db.connection import init_db as _init_db
from shared.db.connection import get_connection as _get_connection
from shared.db.connection import set_database_path as _set_database_path


def init_db() -> None:
    _init_db()


def set_database_path(path: Path) -> None:
    _set_database_path(path)


def get_connection():
    return _get_connection()

__all__ = ["init_db", "set_database_path", "get_connection"]
