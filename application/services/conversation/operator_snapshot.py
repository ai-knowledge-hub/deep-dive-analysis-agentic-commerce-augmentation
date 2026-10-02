"""Server-owned execution snapshot for read-only operator conversations."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Callable

from application.ports.deps import AppDeps
from application.services.agent_runtime.events import list_agent_run_events_page


MAX_ACTIONS = 500
MAX_EVENTS = 500
MAX_NOTE_LENGTH = 500
MAX_COMPLETION_EVIDENCE = 25
MAX_EXPERIMENT_VARIANTS = 100
MAX_EXPERIMENT_RUNS = 100
MAX_EXPERIMENT_METRICS = 100
MAX_EXPERIMENT_VALIDATIONS = 100
MAX_EXPERIMENT_RECOMMENDATIONS = 50


def build_operator_snapshot(
    *,
    deps: AppDeps,
    completion_reader: Callable[..., dict[str, Any] | None],
    tenant_id: str,
    principal_id: str,
    run_id: str,
) -> dict[str, Any]:
    """Build an immutable, tenant-scoped view from authoritative repositories."""

    run = deps.agent_runs.get_agent_run(run_id=run_id, client_id=tenant_id)
    if run is None:
        raise LookupError("Agent run not found")

    action_rows = deps.agent_actions.list_agent_actions(
        agent_run_id=run_id, limit=MAX_ACTIONS + 1
    )
    actions_complete = len(action_rows) <= MAX_ACTIONS
    actions = action_rows[:MAX_ACTIONS]
    page = list_agent_run_events_page(
        deps=deps,
        run_id=run_id,
        client_id=tenant_id,
        limit=MAX_EVENTS,
    )
    event_payload = page.to_dict()
    completion, completion_warnings = _completion_view(
        completion_reader=completion_reader,
        tenant_id=tenant_id,
        run_id=run_id,
    )

    approvals: list[dict[str, Any]] = []
    effects: list[dict[str, Any]] = []
    effect_provenance: dict[str, dict[str, Any]] = {}
    for action in actions:
        action_id = str(action["id"])
        approval = deps.approval_ledger.get_current_approval_for_action(
            tenant_id=tenant_id, workflow_id=run_id, action_id=action_id
        )
        if approval:
            approvals.append(
                {
                    "approval_id": approval.get("approval_id"),
                    "action_id": action_id,
                    "status": approval.get("status"),
                    "sequence": approval.get("sequence"),
                    "updated_at": approval.get("updated_at"),
                }
            )
        effect = deps.approval_ledger.get_effect_execution_for_action(
            tenant_id=tenant_id, workflow_id=run_id, action_id=action_id
        )
        if effect:
            effect_provenance[action_id] = effect
            effects.append(
                {
                    "execution_id": effect.get("execution_id"),
                    "action_id": action_id,
                    "status": effect.get("status"),
                    "receipt_id": effect.get("receipt_id"),
                    "error_code": effect.get("error_code"),
                    "started_at": effect.get("started_at"),
                    "completed_at": effect.get("completed_at"),
                }
            )

    experiment, experiment_completeness, experiment_warnings = _experiment_context(
        deps=deps,
        tenant_id=tenant_id,
        experiment_id=run.get("experiment_id"),
    )
    (
        validation_jobs,
        validation_jobs_completeness,
        validation_job_warnings,
    ) = _linked_validation_jobs(
        deps=deps,
        tenant_id=tenant_id,
        actions=actions,
        effect_provenance=effect_provenance,
    )
    warnings: list[dict[str, str]] = []
    if page.has_more_before:
        warnings.append(
            {
                "code": "event_history_truncated",
                "message": f"Only the latest {MAX_EVENTS} run events are included.",
            }
        )
    if not actions_complete:
        warnings.append(
            {
                "code": "action_history_truncated",
                "message": f"Only the first {MAX_ACTIONS} run actions are included.",
            }
        )
    warnings.extend(completion_warnings)
    warnings.extend(experiment_warnings)
    warnings.extend(validation_job_warnings)

    completion_evidence_completeness = completion.get("evidence_completeness") or {
        "state": "unavailable",
        "included_count": 0,
        "has_more": None,
    }
    completion_state = _completion_completeness_state(completion)

    core = {
        "contract": "operator-execution-snapshot.v1",
        "scope": {"tenant_id": tenant_id, "principal_id": principal_id},
        "run": _run_view(run),
        "actions": [_action_view(action) for action in actions],
        "events": [_event_view(event) for event in event_payload["events"]],
        "event_page": event_payload["page"],
        "approvals": approvals,
        "effects": effects,
        "experiment": experiment,
        "validation_jobs": validation_jobs,
        "completion": completion,
        "completeness": {
            "actions_complete": actions_complete,
            "events_complete": not page.has_more_before,
            "completion_available": bool(
                completion.get("authoritative_decision")
                and (completion.get("projection") or {}).get("state") == "current"
            ),
            "completion": {"state": completion_state},
            "completion_evidence": completion_evidence_completeness,
            "experiment": experiment_completeness,
            "validation_jobs": validation_jobs_completeness,
        },
        "warnings": warnings,
        "navigation": _navigation(run),
    }
    digest = _digest(core)
    return {
        **core,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_digest": digest,
        "authority_fence": _authority_fence(core),
    }


def _completion_view(
    *,
    completion_reader: Callable[..., dict[str, Any] | None],
    tenant_id: str,
    run_id: str,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    try:
        view = completion_reader(tenant_id=tenant_id, workflow_id=run_id)
    except Exception:
        return (
            {
                "state": "unavailable",
                "authoritative_decision": None,
                "evidence_completeness": {
                    "state": "unavailable",
                    "included_count": 0,
                    "has_more": None,
                },
            },
            [
                {
                    "code": "completion_integrity_unavailable",
                    "message": "Verified completion evidence is unavailable or failed integrity checks.",
                }
            ],
        )
    if view is None:
        return (
            {
                "state": "missing",
                "authoritative_decision": None,
                "evidence": [],
                "evidence_completeness": {
                    "state": "complete",
                    "included_count": 0,
                    "has_more": False,
                },
            },
            [
                {
                    "code": "completion_authority_missing",
                    "message": "No authoritative completion record is available for this run.",
                }
            ],
        )
    evidence_rows = view.get("evidence")
    evidence_available = isinstance(evidence_rows, list)
    evidence_values = evidence_rows if evidence_available else []
    evidence_has_more = len(evidence_values) > MAX_COMPLETION_EVIDENCE
    warnings: list[dict[str, str]] = []
    if evidence_has_more:
        warnings.append(
            {
                "code": "completion_evidence_truncated",
                "message": f"Only the first {MAX_COMPLETION_EVIDENCE} completion evidence records are included.",
            }
        )
    mapped = {
        "state": view.get("authority_state", "unknown"),
        "authoritative_decision": view.get("authoritative_decision"),
        "accepted_results": view.get("accepted_results", []),
        "evidence": evidence_values[:MAX_COMPLETION_EVIDENCE],
        "evidence_completeness": {
            "state": (
                "partial"
                if evidence_has_more
                else "complete"
                if evidence_available
                else "unavailable"
            ),
            "included_count": min(len(evidence_values), MAX_COMPLETION_EVIDENCE),
            "available_count": len(evidence_values) if evidence_available else None,
            "has_more": evidence_has_more if evidence_available else None,
        },
        "projection": view.get("projection"),
        "repair": view.get("repair"),
    }
    if not mapped["authoritative_decision"]:
        return (
            mapped,
            [
                *warnings,
                {
                    "code": "completion_authority_missing",
                    "message": "No authoritative completion decision is available for this run.",
                },
            ],
        )
    if (mapped.get("projection") or {}).get("state") != "current":
        return (
            mapped,
            [
                *warnings,
                {
                    "code": "completion_projection_not_current",
                    "message": "Completion evidence exists, but its operator projection is not current.",
                },
            ],
        )
    return mapped, warnings


def _completion_completeness_state(completion: dict[str, Any]) -> str:
    if completion.get("state") == "unavailable":
        return "unavailable"
    if not completion.get("authoritative_decision"):
        return "missing"
    if (completion.get("projection") or {}).get("state") != "current":
        return "partial"
    return "complete"


def _experiment_context(
    *, deps: AppDeps, tenant_id: str, experiment_id: Any
) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, str]]]:
    if not experiment_id:
        return None, {"state": "not_applicable", "sources": {}}, []
    normalized_id = str(experiment_id)
    try:
        experiment = deps.experiments.get_experiment(
            experiment_id=normalized_id, client_id=tenant_id
        )
    except Exception:
        return (
            None,
            {"state": "unavailable", "sources": {}},
            [
                {
                    "code": "linked_experiment_unavailable",
                    "message": "The linked experiment could not be read from its authoritative store.",
                }
            ],
        )
    if not experiment:
        return (
            None,
            {"state": "missing", "sources": {}},
            [
                {
                    "code": "linked_experiment_missing",
                    "message": "The run names an experiment that is missing from the authorized tenant scope.",
                }
            ],
        )

    loaders = {
        "variants": (
            MAX_EXPERIMENT_VARIANTS,
            lambda: deps.experiments.list_variants(
                experiment_id=normalized_id, client_id=tenant_id
            ),
        ),
        "runs": (
            MAX_EXPERIMENT_RUNS,
            lambda: deps.experiment_runs.list_runs(
                experiment_id=normalized_id, limit=MAX_EXPERIMENT_RUNS + 1
            ),
        ),
        "metrics": (
            MAX_EXPERIMENT_METRICS,
            lambda: deps.experiment_runs.list_metrics(
                experiment_id=normalized_id, limit=MAX_EXPERIMENT_METRICS + 1
            ),
        ),
        "validations": (
            MAX_EXPERIMENT_VALIDATIONS,
            lambda: deps.experiment_validations.list_validations(
                experiment_id=normalized_id,
                client_id=tenant_id,
                limit=MAX_EXPERIMENT_VALIDATIONS + 1,
            ),
        ),
        "recommendations": (
            MAX_EXPERIMENT_RECOMMENDATIONS,
            lambda: deps.experiment_recommendations.list_recommendations(
                experiment_id=normalized_id,
                limit=MAX_EXPERIMENT_RECOMMENDATIONS + 1,
            ),
        ),
    }
    values: dict[str, list[dict[str, Any]]] = {}
    sources: dict[str, dict[str, Any]] = {}
    warnings: list[dict[str, str]] = []
    for source, (limit, loader) in loaders.items():
        try:
            rows = list(loader())
        except Exception:
            values[source] = []
            sources[source] = {
                "state": "unavailable",
                "included_count": 0,
                "has_more": None,
            }
            warnings.append(
                {
                    "code": f"experiment_{source}_unavailable",
                    "message": f"Linked experiment {source} could not be read from its authoritative store.",
                }
            )
            continue
        has_more = len(rows) > limit
        values[source] = rows[:limit]
        sources[source] = {
            "state": "partial" if has_more else "complete",
            "included_count": len(values[source]),
            "has_more": has_more,
        }
        if has_more:
            warnings.append(
                {
                    "code": f"experiment_{source}_truncated",
                    "message": f"Only the latest {limit} linked experiment {source} are included.",
                }
            )

    known_variants = {str(item.get("id")) for item in values["variants"]}
    contradictory_sources: set[str] = set()
    for source in ("runs", "metrics", "validations"):
        for item in values[source]:
            if str(item.get("experiment_id") or "") != normalized_id:
                contradictory_sources.add(source)
            variant_id = str(item.get("variant_id") or "")
            if (
                variant_id
                and sources["variants"]["state"] == "complete"
                and variant_id not in known_variants
            ):
                contradictory_sources.add(source)
    for item in values["recommendations"]:
        if str(item.get("experiment_id") or "") != normalized_id:
            contradictory_sources.add("recommendations")
    for source in sorted(contradictory_sources):
        rejected_count = len(values[source])
        values[source] = []
        sources[source]["state"] = "contradictory"
        sources[source]["included_count"] = 0
        sources[source]["rejected_count"] = rejected_count
        warnings.append(
            {
                "code": f"experiment_{source}_contradictory",
                "message": f"Linked experiment {source} contains identities that contradict the authorized experiment graph.",
            }
        )

    states = {item["state"] for item in sources.values()}
    state = (
        "contradictory"
        if "contradictory" in states
        else "unavailable"
        if "unavailable" in states
        else "partial"
        if "partial" in states
        else "complete"
    )
    return (
        {
            "id": experiment["id"],
            "name": experiment.get("name"),
            "status": experiment.get("status"),
            "hypothesis": experiment.get("hypothesis") or {},
            **values,
        },
        {"state": state, "sources": sources},
        warnings,
    )


def _linked_validation_jobs(
    *,
    deps: AppDeps,
    tenant_id: str,
    actions: list[dict[str, Any]],
    effect_provenance: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, str]]]:
    jobs: list[dict[str, Any]] = []
    requested: dict[str, dict[str, set[str]]] = {}
    contradictory: set[str] = set()
    invalid_link_count = 0
    for action in actions:
        action_id = str(action["id"])
        column_has_link = action.get("validation_job_id") is not None
        column_job_id = _canonical_optional_identifier(
            action.get("validation_job_id")
        )
        outputs = action.get("outputs")
        output_has_link = type(outputs) is dict and "validation_job_id" in outputs
        output_job_id = (
            _canonical_optional_identifier(outputs.get("validation_job_id"))
            if output_has_link
            else None
        )
        if (column_has_link and column_job_id is None) or (
            output_has_link and output_job_id is None
        ):
            invalid_link_count += 1
        for job_id, source in (
            (column_job_id, "column"),
            (output_job_id, "output"),
        ):
            if job_id is not None:
                requested.setdefault(job_id, {}).setdefault(action_id, set()).add(
                    source
                )
        if column_job_id and output_job_id and column_job_id != output_job_id:
            contradictory.update((column_job_id, output_job_id))

    missing: list[str] = []
    unavailable: list[str] = []
    for job_id, action_sources in requested.items():
        if job_id in contradictory:
            continue
        try:
            job = deps.validation_jobs.get_job(job_id=job_id, client_id=tenant_id)
        except Exception:
            unavailable.append(job_id)
            continue
        if not job:
            missing.append(job_id)
            continue
        returned_id = str(job.get("id") or "")
        returned_tenant = str(job.get("client_id") or "")
        linked_action_id = str(job.get("agent_action_id") or "")
        if (
            returned_id != job_id
            or returned_tenant != tenant_id
            or (linked_action_id and linked_action_id not in action_sources)
            or any(
                "output" in sources
                and not _matches_runtime_validation_provenance(
                    tenant_id=tenant_id,
                    action_id=action_id,
                    job_id=job_id,
                    job=job,
                    effect=effect_provenance.get(action_id),
                )
                for action_id, sources in action_sources.items()
            )
        ):
            contradictory.add(job_id)
            continue
        jobs.append(
            {
                key: job.get(key)
                for key in (
                    "id",
                    "entity_type",
                    "entity_id",
                    "provider",
                    "mode",
                    "model",
                    "status",
                    "integration_type",
                    "callback_verified",
                    "agent_action_id",
                    "approval_id",
                    "approval_effect_execution_id",
                    "created_at",
                    "updated_at",
                )
            }
        )

    state = (
        "contradictory"
        if contradictory or invalid_link_count
        else "unavailable"
        if unavailable
        else "missing"
        if missing
        else "complete"
    )
    completeness = {
        "state": state,
        "requested_count": len(requested),
        "included_count": len(jobs),
        "missing_count": len(missing),
        "unavailable_count": len(unavailable),
        "contradictory_count": len(contradictory) + invalid_link_count,
    }
    warnings: list[dict[str, str]] = []
    if missing:
        warnings.append(
            {
                "code": "linked_validation_jobs_missing",
                "message": f"{len(missing)} linked validation job(s) are missing from the authorized tenant scope.",
            }
        )
    if unavailable:
        warnings.append(
            {
                "code": "linked_validation_jobs_unavailable",
                "message": f"{len(unavailable)} linked validation job(s) could not be read from the authoritative store.",
            }
        )
    if contradictory or invalid_link_count:
        warnings.append(
            {
                "code": "linked_validation_jobs_contradictory",
                "message": f"{len(contradictory) + invalid_link_count} linked validation job reference(s) contradict the authorized action, effect, or tenant scope.",
            }
        )
    return jobs, completeness, warnings


def _canonical_optional_identifier(value: Any) -> str | None:
    if type(value) is not str or not value or value != value.strip():
        return None
    return value


def _matches_runtime_validation_provenance(
    *,
    tenant_id: str,
    action_id: str,
    job_id: str,
    job: dict[str, Any],
    effect: dict[str, Any] | None,
) -> bool:
    if effect is None:
        return False
    return bool(
        effect.get("tenant_id") == tenant_id
        and effect.get("action_id") == action_id
        and effect.get("status") == "succeeded"
        and effect.get("receipt_id") == f"validation-job:{job_id}"
        and job.get("agent_action_id") == action_id
        and job.get("approval_id") == effect.get("approval_id")
        and job.get("effect_idempotency_key")
        == effect.get("effect_idempotency_key")
        and job.get("approval_effect_execution_id") == effect.get("execution_id")
    )


def _run_view(run: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "brand_id",
        "product_id",
        "experiment_id",
        "objective",
        "run_mode",
        "state",
        "status",
        "active_graph_revision",
        "harness_id",
        "policy_profile_id",
        "registry_version",
        "registry_fingerprint",
        "error",
        "created_at",
        "updated_at",
        "last_heartbeat_at",
    )
    return {key: run.get(key) for key in keys}


def _action_view(action: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "sequence",
        "status",
        "capability_name",
        "capability_version",
        "rationale",
        "confidence",
        "hypothesis_id",
        "variant_id",
        "validation_job_id",
        "effect_class",
        "receipt_id",
        "retry_count",
        "error",
        "created_at",
        "updated_at",
    )
    return {key: action.get(key) for key in keys}


def _event_view(event: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "action_id",
        "sequence",
        "event_type",
        "status",
        "capability_name",
        "effect_class",
        "timestamp",
        "is_policy_event",
        "anchors",
    )
    payload = {key: event.get(key) for key in keys}
    note = event.get("note")
    payload["note"] = str(note)[:MAX_NOTE_LENGTH] if note else None
    return payload


def _navigation(run: dict[str, Any]) -> list[dict[str, str]]:
    run_id = str(run["id"])
    links = [
        {"label": "Run workspace", "href": f"/runs?run_id={run_id}"},
        {"label": "Interventions", "href": f"/interventions?run_id={run_id}"},
    ]
    experiment_id = run.get("experiment_id")
    if experiment_id:
        links.extend(
            [
                {
                    "label": "Experiment",
                    "href": f"/experiments?experiment_id={experiment_id}&run_id={run_id}",
                },
                {
                    "label": "Validation",
                    "href": f"/validation?experiment_id={experiment_id}&run_id={run_id}",
                },
                {
                    "label": "Evidence",
                    "href": f"/evidence?experiment_id={experiment_id}&run_id={run_id}",
                },
            ]
        )
    return links


def _authority_fence(snapshot: dict[str, Any]) -> str:
    # The canonical core excludes fetched_at, so any material run, action,
    # event, approval, effect, evidence, or completion change advances the fence.
    return _digest(snapshot)


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


__all__ = ["build_operator_snapshot"]
