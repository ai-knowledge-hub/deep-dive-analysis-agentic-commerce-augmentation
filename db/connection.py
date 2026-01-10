"""Re-export from shared.db for backward compatibility.

DEPRECATED: Import from shared.db.connection instead.
"""

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
