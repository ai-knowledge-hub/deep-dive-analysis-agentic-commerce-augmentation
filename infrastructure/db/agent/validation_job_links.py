"""Transactional validation of action-to-validation-job effect provenance."""

from __future__ import annotations

import sqlite3


def validation_job_link_conflict(
    *,
    conn: sqlite3.Connection,
    linked_validation_job_id: str | None,
    existing_validation_job_id: str | None,
    tenant_id: str,
    action_id: str,
    approval_id: str,
    effect_idempotency_key: str,
    execution_id: str,
    receipt_id: str,
) -> str | None:
    if linked_validation_job_id is None:
        return None
    if existing_validation_job_id not in {None, linked_validation_job_id}:
        return "action is already linked to different validation evidence"
    job_row = conn.execute(
        """
        SELECT client_id, agent_action_id, approval_id,
               effect_idempotency_key, approval_effect_execution_id
        FROM validation_jobs
        WHERE id = ?
        """,
        (linked_validation_job_id,),
    ).fetchone()
    expected = {
        "client_id": tenant_id,
        "agent_action_id": action_id,
        "approval_id": approval_id,
        "effect_idempotency_key": effect_idempotency_key,
        "approval_effect_execution_id": execution_id,
    }
    if (
        job_row is None
        or receipt_id != f"validation-job:{linked_validation_job_id}"
        or any(job_row[field] != value for field, value in expected.items())
    ):
        return "validation job does not match the authorized effect"
    return None


__all__ = ["validation_job_link_conflict"]
