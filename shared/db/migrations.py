"""Lightweight SQLite migration runner."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import sqlite3

MIGRATIONS_PATH = Path(__file__).resolve().parent / "migrations"


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        (name,),
    ).fetchone()
    return row is not None


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row["name"] == column for row in rows)


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            name TEXT PRIMARY KEY,
            applied_at TEXT DEFAULT (datetime('now'))
        )
        """
    )


def _applied_migrations(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM schema_migrations").fetchall()
    return {row["name"] for row in rows}


def _mark_applied(conn: sqlite3.Connection, name: str) -> None:
    conn.execute(
        "INSERT OR IGNORE INTO schema_migrations (name) VALUES (?)",
        (name,),
    )


def _should_apply_multi_tenant(conn: sqlite3.Connection) -> bool:
    if not _table_exists(conn, "clients"):
        return True
    if not _table_exists(conn, "sessions"):
        return False
    return not _column_exists(conn, "sessions", "client_id")


def _iter_migration_files(path: Path) -> Iterable[Path]:
    if not path.exists():
        return []
    return sorted(path.glob("*.sql"))


def apply_migrations(
    conn: sqlite3.Connection, migrations_path: Path | None = None
) -> None:
    """Apply pending migrations in order."""
    _ensure_migrations_table(conn)
    applied = _applied_migrations(conn)
    path = migrations_path or MIGRATIONS_PATH
    for migration in _iter_migration_files(path):
        name = migration.name
        should_apply = name == "001_multi_tenant.sql" and _should_apply_multi_tenant(
            conn
        )
        if name in applied and not should_apply:
            continue
        if name == "001_multi_tenant.sql" and not should_apply:
            _mark_applied(conn, name)
            continue
        script = migration.read_text(encoding="utf-8")
        conn.executescript(script)
        _mark_applied(conn, name)
    conn.commit()


__all__ = ["apply_migrations", "MIGRATIONS_PATH"]
