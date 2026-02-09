from __future__ import annotations

from typing import Any

from infrastructure.db.connection import get_connection
from infrastructure.db.tenancy import ensure_client


def consume_token(
    *,
    token_hash: str,
    client_id: str,
    job_id: str,
    provider_run_id: str,
) -> bool:
    """Persist a callback token hash exactly once.

    Returns True when the token hash was newly consumed, False when already used.
    """
    ensure_client(client_id)
    conn = get_connection()
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO validation_callback_tokens (
            token_hash,
            client_id,
            job_id,
            provider_run_id
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            token_hash,
            client_id,
            job_id,
            provider_run_id,
        ),
    )
    conn.commit()
    return bool(cursor.rowcount)


__all__ = ["consume_token"]
