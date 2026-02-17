from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from application.ports.deps import AppDeps
from application.services.experiment.runner import ExperimentRunner


@dataclass(frozen=True)
class CapabilityContext:
    client_id: str
    user_id: Optional[str]


class CapabilityExecutionError(ValueError):
    pass


def execute_capability(
    *,
    deps: AppDeps,
    context: CapabilityContext,
    capability_name: str,
    inputs: Dict[str, Any],
) -> Dict[str, Any]:
    name = str(capability_name or "").strip()
    if name == "freeze_retrieval_protocol":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError(
                "freeze_retrieval_protocol requires experiment_id"
            )
        retrieval_max_results = int(inputs.get("retrieval_max_results") or 5)
        runner = ExperimentRunner(deps=deps)
        return runner.freeze_retrieval_protocol(
            experiment_id=experiment_id,
            client_id=context.client_id,
            user_id=context.user_id,
            retrieval_max_results=retrieval_max_results,
        )
    if name == "run_control_baseline":
        experiment_id = str(inputs.get("experiment_id") or "").strip()
        if not experiment_id:
            raise CapabilityExecutionError("run_control_baseline requires experiment_id")
        control_variant_id = _resolve_control_variant_id(
            deps=deps, experiment_id=experiment_id
        )
        if not control_variant_id:
            raise CapabilityExecutionError(
                "run_control_baseline could not find a control variant"
            )
        retrieval_max_results = int(inputs.get("retrieval_max_results") or 5)
        runner = ExperimentRunner(deps=deps)
        result = runner.run_experiment(
            experiment_id=experiment_id,
            variant_id=control_variant_id,
            client_id=context.client_id,
            user_id=context.user_id,
            execution_mode="retrieval_backed",
            retrieval_max_results=retrieval_max_results,
        )
        return {
            "experiment_id": experiment_id,
            "variant_id": control_variant_id,
            "execution_mode": "retrieval_backed",
            "snapshot_version": (result.metrics or {}).get("snapshot_version"),
            "total_runs": (result.metrics or {}).get("total_runs"),
            "win_rate": (result.metrics or {}).get("win_rate"),
            "metric_id": (result.metrics or {}).get("metric_id"),
            "status": "baseline_scored",
        }

    raise CapabilityExecutionError(f"Unsupported capability: {name}")


def _resolve_control_variant_id(*, deps: AppDeps, experiment_id: str) -> str | None:
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


__all__ = [
    "CapabilityContext",
    "CapabilityExecutionError",
    "execute_capability",
]
