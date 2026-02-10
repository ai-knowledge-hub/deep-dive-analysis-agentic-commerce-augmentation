from __future__ import annotations

from typing import Any, Dict, List

from application.ports.deps import AppDeps


class ExperimentExecutionStateService:
    def __init__(self, *, deps: AppDeps) -> None:
        self._deps = deps

    def get_state(self, *, experiment_id: str, client_id: str) -> Dict[str, Any]:
        experiment = self._deps.experiments.get_experiment(
            experiment_id=experiment_id, client_id=client_id
        )
        if not experiment:
            raise ValueError("experiment not found")

        battery_id = experiment.get("battery_id")
        queries = (
            self._deps.query_batteries.list_queries(battery_id=battery_id)
            if battery_id
            else []
        )
        enabled_queries = [item for item in queries if item.get("enabled")]
        variants = self._deps.experiments.list_variants(experiment_id=experiment_id)
        runs = self._deps.experiment_runs.list_runs(experiment_id=experiment_id, limit=1000)
        metrics = self._deps.experiment_runs.list_metrics(
            experiment_id=experiment_id, limit=1000
        )
        validations = self._deps.experiment_validations.list_validations(
            experiment_id=experiment_id,
            client_id=client_id,
            limit=1000,
        )

        phases = self._compute_phases(
            experiment=experiment,
            enabled_queries=enabled_queries,
            variants=variants,
            runs=runs,
            metrics=metrics,
            validations=validations,
            client_id=client_id,
        )
        phase_order: List[str] = [
            "battery_ready",
            "retrieval_snapshots_ready",
            "baseline_scored",
            "hypotheses_ready",
            "variants_ready",
            "experiment_run_completed",
            "validation_completed",
            "posterior_updated",
        ]
        pending = next((name for name in phase_order if not phases[name]["done"]), None)
        next_action = pending or "complete"

        return {
            "experiment_id": experiment_id,
            "client_id": client_id,
            "phase_order": phase_order,
            "phases": phases,
            "next_action": next_action,
            "complete": pending is None,
        }

    def _compute_phases(
        self,
        *,
        experiment: Dict[str, Any],
        enabled_queries: List[Dict[str, Any]],
        variants: List[Dict[str, Any]],
        runs: List[Dict[str, Any]],
        metrics: List[Dict[str, Any]],
        validations: List[Dict[str, Any]],
        client_id: str,
    ) -> Dict[str, Dict[str, Any]]:
        battery_ready = bool(experiment.get("battery_id")) and len(enabled_queries) > 0

        retrieval_runs = [
            run
            for run in runs
            if str(run.get("execution_mode") or "").strip().lower() == "retrieval_backed"
        ]
        retrieval_snapshots_ready = any(
            _to_int((run.get("retrieval_summary") or {}).get("candidate_count")) > 0
            for run in retrieval_runs
        )

        hypothesis = experiment.get("hypothesis") or {}
        candidate_variant_exists = any(
            (
                str((item.get("payload") or {}).get("role") or "").strip().lower()
                == "candidate"
            )
            or (
                isinstance(item.get("label"), str)
                and (
                    "candidate" in item.get("label", "").lower()
                    or "hypothesis" in item.get("label", "").lower()
                )
            )
            for item in variants
        )
        hypotheses_ready = bool(hypothesis) or candidate_variant_exists

        control_variant_ids = [
            item.get("id")
            for item in variants
            if isinstance(item.get("label"), str)
            and "control" in item.get("label", "").lower()
        ]
        baseline_scored = any(
            metric.get("variant_id") in control_variant_ids for metric in metrics
        )

        variants_ready = len(variants) >= 2
        experiment_run_completed = len(runs) > 0 and len(metrics) > 0
        validation_completed = len(validations) > 0

        posterior_updated = False
        brand_id = experiment.get("brand_id")
        if brand_id:
            latest = self._deps.brand_beliefs.latest_belief(
                client_id=client_id, brand_id=brand_id
            )
            if latest:
                evidence = latest.get("evidence") or {}
                metadata = latest.get("metadata") or {}
                posterior_updated = (
                    evidence.get("experiment_id") == experiment.get("id")
                    or metadata.get("experiment_id") == experiment.get("id")
                )

        return {
            "battery_ready": {
                "done": battery_ready,
                "detail": f"{len(enabled_queries)} enabled queries",
            },
            "retrieval_snapshots_ready": {
                "done": retrieval_snapshots_ready,
                "detail": f"{len(retrieval_runs)} retrieval-backed runs",
            },
            "baseline_scored": {
                "done": baseline_scored,
                "detail": "Control variant has scored metrics",
            },
            "hypotheses_ready": {
                "done": hypotheses_ready,
                "detail": "Candidate hypothesis/variant is defined",
            },
            "variants_ready": {
                "done": variants_ready,
                "detail": f"{len(variants)} variants",
            },
            "experiment_run_completed": {
                "done": experiment_run_completed,
                "detail": f"{len(runs)} runs / {len(metrics)} metric rows",
            },
            "validation_completed": {
                "done": validation_completed,
                "detail": f"{len(validations)} validations logged",
            },
            "posterior_updated": {
                "done": posterior_updated,
                "detail": "Latest brand belief references this experiment",
            },
        }


def _to_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


__all__ = ["ExperimentExecutionStateService"]
