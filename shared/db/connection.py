"""SQLite connection helpers for discovery-first memory storage."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path
from threading import Lock
from threading import local
from threading import get_ident
from typing import Callable, Iterator, Optional

from shared.db.migrations import apply_migrations

SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"
DEFAULT_DB_PATH = Path(os.getenv("DATABASE_PATH", "./db/discovery.db")).resolve()

_lock = Lock()
_thread_local = local()
_connections_by_thread: dict[int, sqlite3.Connection] = {}


def _create_connection() -> sqlite3.Connection:
    DEFAULT_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        DEFAULT_DB_PATH,
        detect_types=sqlite3.PARSE_DECLTYPES,
        check_same_thread=True,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def set_database_path(path: str | Path) -> None:
    """Override the default DB path (useful for tests)."""
    global DEFAULT_DB_PATH
    resolved = Path(path).resolve()
    DEFAULT_DB_PATH = resolved
    with _lock:
        for conn in _connections_by_thread.values():
            try:
                conn.close()
            except sqlite3.ProgrammingError:
                # Connection belongs to another thread; drop reference and let thread clean up.
                pass
        _connections_by_thread.clear()
        if hasattr(_thread_local, "conn"):
            delattr(_thread_local, "conn")


def get_connection() -> sqlite3.Connection:
    """Return a per-thread SQLite connection to avoid cross-thread API misuse."""
    conn: Optional[sqlite3.Connection] = getattr(_thread_local, "conn", None)
    if conn is not None:
        return conn
    with _lock:
        conn = _create_connection()
        _thread_local.conn = conn
        _connections_by_thread[get_ident()] = conn
        return conn


def init_db(schema_path: Path | None = None) -> None:
    """Initialize the database schema from schema.sql."""
    conn = get_connection()
    schema_file = schema_path or SCHEMA_PATH
    has_sessions = (
        conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='sessions'"
        ).fetchone()
        is not None
    )
    if not has_sessions:
        with schema_file.open("r", encoding="utf-8") as f:
            script = f.read()
        conn.executescript(script)
    apply_migrations(conn)
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
