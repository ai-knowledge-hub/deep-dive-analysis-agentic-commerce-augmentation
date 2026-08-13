from __future__ import annotations

from typing import Any, Mapping, Sequence

from application.services.agent_runtime.planner import build_initial_plan
from application.services.agent_runtime.registry import get_capability_spec
from application.services.agent_runtime.release_policy import (
    BetaReleaseGateError,
    assert_beta_capability_available,
)


class AgentRunPlanError(ValueError):
    pass


def validate_plan_capabilities(
    allowed_capabilities: Sequence[str], *, objective: Mapping[str, Any]
) -> None:
    requested = [
        str(capability).strip()
        for capability in allowed_capabilities
        if str(capability).strip()
    ]
    unsupported = [item for item in requested if not get_capability_spec(item)]
    if unsupported:
        raise AgentRunPlanError(
            "Unsupported allowed_capabilities: " + ", ".join(unsupported)
        )
    try:
        for capability_name in requested:
            spec = get_capability_spec(capability_name)
            if spec is not None:
                assert_beta_capability_available(
                    capability_name,
                    tool_id=spec.tool_id,
                    effect_class=spec.effect_class,
                )
    except BetaReleaseGateError as exc:
        raise AgentRunPlanError(str(exc)) from exc
    if requested and not build_initial_plan(
        experiment_id=None,
        allowed_capabilities=requested,
        capability_versions={},
        objective=dict(objective),
    ):
        raise AgentRunPlanError(
            "allowed_capabilities did not produce any initial plan actions"
        )


__all__ = ["AgentRunPlanError", "validate_plan_capabilities"]
