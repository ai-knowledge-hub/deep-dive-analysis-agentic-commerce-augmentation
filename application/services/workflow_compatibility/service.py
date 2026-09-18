"""Application boundary for the non-authoritative workflow shadow."""

from __future__ import annotations

import logging
from typing import Any

from application.ports.workflow_compatibility import WorkflowCompatibilityStore


logger = logging.getLogger(__name__)


def project_sequential_run_best_effort(
    *,
    store: WorkflowCompatibilityStore,
    tenant_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Project a run without making the shadow a creation safety boundary."""

    try:
        return store.project_sequential_run(tenant_id=tenant_id, run_id=run_id)
    except Exception as exc:  # the legacy runtime must remain available
        logger.exception("Sequential workflow compatibility projection failed")
        try:
            return store.record_projection_failure(
                tenant_id=tenant_id,
                run_id=run_id,
                error_code=type(exc).__name__,
            )
        except Exception:
            logger.exception("Workflow projection failure could not be persisted")
            return {
                "outcome": "failed_unrecorded",
                "tenant_id": tenant_id,
                "workflow_id": run_id,
                "error_code": type(exc).__name__,
            }


def reconcile_sequential_projections_best_effort(
    *,
    store: WorkflowCompatibilityStore,
    tenant_id: str,
    limit: int = 25,
) -> dict[str, Any]:
    """Bound restart/backfill work without becoming a scheduler dependency."""

    bounded_limit = max(1, min(int(limit), 100))
    try:
        candidates = store.list_projection_candidates(
            tenant_id=tenant_id,
            limit=bounded_limit,
        )
    except Exception as exc:
        logger.exception("Workflow compatibility candidate scan failed")
        return {
            "outcome": "scan_failed",
            "tenant_id": tenant_id,
            "error_code": type(exc).__name__,
            "runs_considered": 0,
            "results": [],
        }
    results = [
        project_sequential_run_best_effort(
            store=store,
            tenant_id=tenant_id,
            run_id=str(candidate["workflow_id"]),
        )
        for candidate in candidates
    ]
    return {
        "outcome": "completed",
        "tenant_id": tenant_id,
        "runs_considered": len(candidates),
        "results": results,
    }


__all__ = [
    "project_sequential_run_best_effort",
    "reconcile_sequential_projections_best_effort",
]
