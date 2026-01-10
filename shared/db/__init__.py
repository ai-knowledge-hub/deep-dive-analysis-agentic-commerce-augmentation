"""Database module - re-exports connection utilities."""

from shared.db.connection import (
    get_connection,
    init_db,
    iter_rows,
    set_database_path,
    with_connection,
)

__all__ = [
    "get_connection",
    "init_db",
    "iter_rows",
    "set_database_path",
    "with_connection",
]
