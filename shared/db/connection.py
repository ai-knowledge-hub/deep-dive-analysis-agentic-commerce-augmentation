"""SQLite connection helpers for empowerment-first memory storage."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import Lock
from typing import Callable, Iterator, Optional

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB_PATH = Path(os.getenv("DATABASE_PATH", "./db/empowerment.db")).resolve()

_connection: Optional[sqlite3.Connection] = None
_lock = Lock()


def set_database_path(path: str | Path) -> None:
    """Override the default DB path (useful for tests)."""
    global DEFAULT_DB_PATH, _connection
    resolved = Path(path).resolve()
    DEFAULT_DB_PATH = resolved
    if _connection is not None:
        with _lock:
            _connection.close()
            _connection = None


def get_connection() -> sqlite3.Connection:
    """Return a singleton SQLite connection configured for concurrency."""
    global _connection
    if _connection is None:
        with _lock:
            if _connection is None:
                DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(
                    DEFAULT_DB_PATH,
                    detect_types=sqlite3.PARSE_DECLTYPES,
                    check_same_thread=False,
                )
                conn.row_factory = sqlite3.Row
                conn.execute("PRAGMA foreign_keys = ON;")
                conn.execute("PRAGMA journal_mode = WAL;")
                _connection = conn
    return _connection


def init_db(schema_path: Path | None = None) -> None:
    """Initialize the database schema from schema.sql."""
    conn = get_connection()
    schema_file = schema_path or SCHEMA_PATH
    with schema_file.open("r", encoding="utf-8") as f:
        script = f.read()
    conn.executescript(script)
    conn.commit()


def with_connection(func: Callable[[sqlite3.Connection], None]) -> None:
    """Helper to run a callable with the shared connection."""
    conn = get_connection()
    func(conn)


def iter_rows(query: str, *params) -> Iterator[sqlite3.Row]:
    """Utility generator for SELECT queries."""
    conn = get_connection()
    cursor = conn.execute(query, params)
    try:
        for row in cursor:
            yield row
    finally:
        cursor.close()


if __name__ == "__main__":
    init_db()
    print(f"Initialized SQLite database at {DEFAULT_DB_PATH}")
