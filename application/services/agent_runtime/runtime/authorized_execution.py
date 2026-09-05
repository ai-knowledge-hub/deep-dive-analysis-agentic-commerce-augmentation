"""Capability execution with exact governed-effect authorization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict

from application.ports.deps import AppDeps
from application.services.agent_runtime.approval_authorization import (
    ExactApprovalAuthorization,
    complete_authorized_effect,
    commit_pre_effect_authorization,
)
from application.services.agent_runtime.capabilities import (
    CapabilityContext,
    CapabilityExecutionError,
)
from application.services.agent_runtime.registry import CapabilitySpec, validate_outputs
from application.services.agent_runtime.runtime.execution import (
    execute_runtime_capability,
)
from application.services.agent_runtime.runtime.payloads import hash_payload


@dataclass
class AuthorizedExecutionState:
    authorization: ExactApprovalAuthorization | None = None
    phase: str = "admission"
    effect_invoked: bool = False


def execute_with_exact_authorization(
    *,
    deps: AppDeps,
    run: Dict[str, Any],
    action: Dict[str, Any],
    spec: CapabilitySpec,
    inputs: Dict[str, Any],
    lock_token: str,
    user_id: str | None,
    state: AuthorizedExecutionState,
) -> Dict[str, Any]:
    state.phase = "pre_effect"
    state.authorization = commit_pre_effect_authorization(
        deps=deps,
        run=run,
        action=action,
        spec=spec,
        executable_inputs=inputs,
        lock_token=lock_token,
    )
    state.effect_invoked = True
    outputs = execute_runtime_capability(
        deps=deps,
        context=CapabilityContext(
            client_id=str(run.get("client_id") or ""),
            user_id=user_id,
            agent_action_id=(
                state.authorization.binding.action_id
                if state.authorization is not None
                else None
            ),
            approval_id=(
                state.authorization.approval_id
                if state.authorization is not None
                else None
            ),
            effect_idempotency_key=(
                state.authorization.effect_idempotency_key
                if state.authorization is not None
                else None
            ),
            approval_effect_execution_id=(
                state.authorization.execution_id
                if state.authorization is not None
                else None
            ),
        ),
        capability_name=spec.name,
        inputs=inputs,
    )
    if state.authorization is None:
        output_errors = validate_outputs(spec, outputs)
        if output_errors:
            raise CapabilityExecutionError("; ".join(output_errors))
    complete_authorized_effect(
        deps=deps,
        run=run,
        action=action,
        authorization=state.authorization,
        outputs=outputs,
        outputs_hash=hash_payload(outputs),
    )
    return outputs


__all__ = ["AuthorizedExecutionState", "execute_with_exact_authorization"]
