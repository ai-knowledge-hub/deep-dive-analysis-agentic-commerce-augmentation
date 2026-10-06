"""Retry-family effect exclusion, read under the effect-start write lock."""

from __future__ import annotations

import sqlite3


def related_effect_started_locked(
    conn: sqlite3.Connection, *, tenant_id: str, workflow_id: str, action_id: str
) -> bool:
    """Include immutable v5 relationships and legacy retry identities.

    Walk both directions so roots, descendants and prequeued siblings share
    one fence. UNION bounds cycles without truncating the family. A started
    or uncertain effect is already consumed, even without a success receipt.
    The caller handles replay of the current exact effect before this check.
    """
    return (
        conn.execute(
            """
        WITH RECURSIVE
        actions AS (
            SELECT action.id, action.dedupe_key FROM agent_actions action
            JOIN agent_runs run ON run.id = action.agent_run_id
            WHERE run.id = :workflow AND run.client_id = :tenant
        ),
        identities AS (
            SELECT id, dedupe_key FROM actions
            UNION
            SELECT action_id, effect_idempotency_key
            FROM approval_effect_executions
            WHERE tenant_id = :tenant AND workflow_id = :workflow
        ),
        links(child, parent) AS (
            SELECT receipt.action_id,
                   json_extract(receipt.receipt_json, '$.source_action_id')
            FROM operator_retry_receipts receipt
            WHERE receipt.tenant_id = :tenant AND receipt.workflow_id = :workflow
            UNION
            SELECT child.id, parent.id FROM identities child JOIN actions parent
              ON substr(child.dedupe_key, 1, length(parent.id) + 7)
                 = 'retry:' || parent.id || ':'
        ),
        edges(a, b) AS (
            SELECT child, parent FROM links UNION SELECT parent, child FROM links
        ),
        family(id) AS (
            SELECT :action UNION
            SELECT edges.b FROM edges JOIN family ON edges.a = family.id
        )
        SELECT 1 FROM approval_effect_executions effect
        JOIN family ON family.id = effect.action_id
        WHERE effect.tenant_id = :tenant AND effect.workflow_id = :workflow
        LIMIT 1
        """,
            {"tenant": tenant_id, "workflow": workflow_id, "action": action_id},
        ).fetchone()
        is not None
    )
