from __future__ import annotations

from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.agent_runtime.capability_types import (
    CapabilityContext,
    CapabilityExecutionError,
)


def resolve_control_variant_id(*, deps: AppDeps, experiment_id: str) -> str | None:
    variants = deps.experiments.list_variants(experiment_id=experiment_id)
    for variant in variants:
        payload = variant.get("payload") or {}
        role = str(payload.get("role") or "").strip().lower()
        if role == "control":
            return str(variant.get("id") or "")
    for variant in variants:
        label = str(variant.get("label") or "").strip().lower()
        if "control" in label:
            return str(variant.get("id") or "")
    return None


def select_candidate_variant_id(
    *, deps: AppDeps, experiment_id: str, strategy: str
) -> str | None:
    variants = deps.experiments.list_variants(experiment_id=experiment_id)
    candidates = [
        v for v in variants if str(v.get("id") or "") and not is_control_variant_row(v)
    ]
    if not candidates:
        return None
    # Current v0 strategies map to newest-first non-control selection.
    # We can later add Thompson/policy-aware selection here.
    if strategy in {"top_1", "latest", "newest"}:
        return str(candidates[0].get("id") or "")
    return str(candidates[0].get("id") or "")


def is_control_variant_row(variant: Dict[str, Any]) -> bool:
    payload = variant.get("payload") or {}
    role = str(payload.get("role") or "").strip().lower()
    if role == "control":
        return True
    label = str(variant.get("label") or "").strip().lower()
    return "control" in label


def build_experiment_validation_payload(
    *,
    deps: AppDeps,
    client_id: str,
    experiment_id: str,
    target_variant_id: Optional[str],
) -> Dict[str, Any]:
    experiment = deps.experiments.get_experiment(
        experiment_id=experiment_id, client_id=client_id
    )
    if not experiment:
        raise CapabilityExecutionError("experiment not found for validation payload")
    runs = deps.experiment_runs.list_runs(experiment_id=experiment_id, limit=500)
    metrics = deps.experiment_runs.list_metrics(experiment_id=experiment_id, limit=500)
    variants = deps.experiments.list_variants(experiment_id=experiment_id)
    return {
        "type": "experiment",
        "experiment": experiment,
        "runs": runs,
        "metrics": metrics,
        "variants": variants,
        "target_variant_id": target_variant_id,
    }


def latest_metric_for_variant(
    *, deps: AppDeps, experiment_id: str, variant_id: str
) -> Dict[str, Any] | None:
    rows = deps.experiment_runs.list_metrics(experiment_id=experiment_id, limit=500)
    for row in rows:
        if str(row.get("variant_id") or "") == str(variant_id):
            return row
    return None


def _extract_observed_coverage(
    *,
    deps: AppDeps,
    experiment: Dict[str, Any],
    experiment_id: str,
    variant_id: str,
    decision_inputs: Dict[str, Any] | None,
) -> float:
    if decision_inputs:
        try:
            return max(0.0, min(1.0, float(decision_inputs.get("coverage_obs") or 0.0)))
        except (TypeError, ValueError):
            pass

    battery_id = str(experiment.get("battery_id") or "").strip()
    queries = deps.batteries.list_queries(battery_id=battery_id) if battery_id else []
    enabled_queries = [
        item
        for item in queries
        if bool(item.get("enabled", True)) and str(item.get("query_text") or "").strip()
    ]
    validations = deps.experiment_validations.list_validations(
        experiment_id=experiment_id, limit=500
    )
    distinct_q = {
        str(v.get("query_text") or "").strip().lower()
        for v in validations
        if str(v.get("variant_id") or "") == str(variant_id)
        and str(v.get("query_text") or "").strip()
    }
    if not enabled_queries:
        return 0.0
    return max(0.0, min(1.0, len(distinct_q) / len(enabled_queries)))


def compute_validation_readiness(
    *,
    deps: AppDeps,
    context: CapabilityContext,
    experiment_id: str,
    variant_id: str,
    prod_min_coverage: float,
    min_verified_runs: int,
    min_synthetic_results: int,
) -> Dict[str, Any]:
    experiment = deps.experiments.get_experiment(
        experiment_id=experiment_id, client_id=context.client_id
    )
    if not experiment:
        raise CapabilityExecutionError("experiment not found")

    latest_metric = latest_metric_for_variant(
        deps=deps,
        experiment_id=experiment_id,
        variant_id=variant_id,
    )
    metric_payload = (latest_metric or {}).get("metrics") or {}
    decision_inputs = (
        metric_payload.get("decision_inputs")
        if isinstance(metric_payload, dict)
        else None
    )
    coverage_obs = _extract_observed_coverage(
        deps=deps,
        experiment=experiment,
        experiment_id=experiment_id,
        variant_id=variant_id,
        decision_inputs=decision_inputs if isinstance(decision_inputs, dict) else None,
    )
    observed_summary = deps.experiment_validations.accuracy_summary(
        experiment_id=experiment_id,
        client_id=context.client_id,
    )
    verified_runs = int(observed_summary.get("verified_runs") or 0)
    jobs = deps.validation_jobs.list_jobs(
        client_id=context.client_id,
        entity_type="experiment_run",
        entity_id=experiment_id,
        limit=200,
    )
    completed_jobs = [
        item for item in jobs if str(item.get("status") or "").lower() == "completed"
    ]
    scored_results = 0
    for job in completed_jobs:
        result = deps.validation_results.get_latest_for_job(
            job_id=str(job.get("id") or "")
        )
        if not result:
            continue
        if result.get("score") is not None or result.get("winner_id"):
            scored_results += 1

    observed_ready = (coverage_obs >= prod_min_coverage) and (
        verified_runs >= min_verified_runs
    )
    synthetic_ready = scored_results >= min_synthetic_results
    promotion_tier = "prod" if observed_ready else "lab"
    readiness_state = (
        "ready_for_prod"
        if observed_ready
        else "ready_for_lab"
        if synthetic_ready
        else "needs_more_validation"
    )
    return {
        "readiness_state": readiness_state,
        "promotion_tier": promotion_tier,
        "observed_ready": observed_ready,
        "synthetic_ready": synthetic_ready,
        "observed": {
            "coverage_obs": round(coverage_obs, 6),
            "verified_runs": verified_runs,
            "correct_runs": int(observed_summary.get("correct_runs") or 0),
            "accuracy": observed_summary.get("accuracy"),
        },
        "synthetic": {
            "jobs_total": len(jobs),
            "jobs_completed": len(completed_jobs),
            "results_scored": scored_results,
        },
        "latest_decision": {
            "decision_action": metric_payload.get("decision_action")
            if isinstance(metric_payload, dict)
            else None,
            "decision_tier": metric_payload.get("decision_tier")
            if isinstance(metric_payload, dict)
            else None,
            "posterior": metric_payload.get("posterior")
            if isinstance(metric_payload, dict)
            else None,
            "decision_policy_version": metric_payload.get("decision_policy_version")
            if isinstance(metric_payload, dict)
            else None,
            "metric_id": (latest_metric or {}).get("id"),
        },
    }


def latest_analytics_event_for_variant(
    *,
    deps: AppDeps,
    client_id: str,
    experiment_id: str,
    variant_id: str,
    event_type: str,
) -> Dict[str, Any] | None:
    events = deps.analytics_events.list_events(
        client_id=client_id,
        experiment_id=experiment_id,
        limit=500,
    )
    for event in events:
        if str(event.get("event_type") or "") != str(event_type):
            continue
        if str(event.get("variant_id") or "") != str(variant_id):
            continue
        return event
    return None


def find_draft_experiment_revision_for_variant(
    *,
    deps: AppDeps,
    client_id: str,
    product_id: str,
    variant_id: str,
) -> Dict[str, Any] | None:
    revisions = deps.copy_revisions.list_revisions(
        client_id=client_id,
        product_id=product_id,
        source_type="experiment",
        limit=200,
    )
    for revision in revisions:
        if str(revision.get("source_variant_id") or "") != str(variant_id):
            continue
        if str(revision.get("status") or "").strip().lower() != "draft":
            continue
        return revision
    return None


def variant_candidate_description(variant: Dict[str, Any]) -> str:
    payload = variant.get("payload") or {}
    if isinstance(payload, dict):
        return str(payload.get("description") or "").strip()
    return ""


def safe_float(value: Any, *, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
