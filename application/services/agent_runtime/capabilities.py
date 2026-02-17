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

    raise CapabilityExecutionError(f"Unsupported capability: {name}")


__all__ = ["CapabilityContext", "CapabilityExecutionError", "execute_capability"]

