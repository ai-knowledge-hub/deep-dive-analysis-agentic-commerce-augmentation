"""Client repository helpers for multi-tenant scoping."""

from __future__ import annotations

from shared.db.connection import get_connection

DEFAULT_CLIENT_ID = "default"


def ensure_client(client_id: str = DEFAULT_CLIENT_ID, name: str | None = None) -> None:
    """Create a client row if it doesn't already exist."""
    conn = get_connection()
    conn.execute(
        """
        INSERT OR IGNORE INTO clients (id, name)
        VALUES (?, ?)
        """,
        (client_id, name or "Default"),
    )
    conn.commit()


__all__ = ["DEFAULT_CLIENT_ID", "ensure_client"]
