"""Tenant/client helpers for multi-tenant scoping."""

from __future__ import annotations

from infrastructure.db.core.connection import get_connection
from infrastructure.db.core.transactions import JoinedTransaction

DEFAULT_CLIENT_ID = "default"


def ensure_client(client_id: str = DEFAULT_CLIENT_ID, name: str | None = None) -> None:
    conn = get_connection()
    transaction = JoinedTransaction(conn, "ensure_client")
    try:
        conn.execute(
            """
            INSERT OR IGNORE INTO clients (id, name)
            VALUES (?, ?)
            """,
            (client_id, name or "Default"),
        )
        transaction.commit()
    except Exception:
        transaction.rollback()
        raise


__all__ = ["DEFAULT_CLIENT_ID", "ensure_client"]
