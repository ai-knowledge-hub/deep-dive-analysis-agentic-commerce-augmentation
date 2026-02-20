from __future__ import annotations

from typing import Any, Iterable, Mapping

from application.services.agent_runtime.registry import CapabilitySpec


class PolicyError(ValueError):
    pass


class PolicyEnforcer:
    def validate_action_execution(
        self,
        *,
        run: Mapping[str, Any],
        action: Mapping[str, Any],
        spec: CapabilitySpec,
        all_actions: Iterable[Mapping[str, Any]],
        inputs: Mapping[str, Any],
    ) -> None:
        self._assert_capability_allowed(run=run, capability_name=spec.name)
        self._assert_required_inputs(spec=spec, inputs=inputs)
        self._assert_budgets(
            run=run,
            all_actions=list(all_actions),
            capability_name=spec.name,
        )

    def _assert_capability_allowed(
        self,
        *,
        run: Mapping[str, Any],
        capability_name: str,
    ) -> None:
        allowed = {
            str(item).strip()
            for item in list(run.get("allowed_capabilities") or [])
            if str(item).strip()
        }
        if capability_name not in allowed:
            raise PolicyError(
                f"Capability '{capability_name}' is not allowed for this run"
            )

    def _assert_required_inputs(
        self,
        *,
        spec: CapabilitySpec,
        inputs: Mapping[str, Any],
    ) -> None:
        missing = []
        for key in spec.required_inputs:
            value = inputs.get(key)
            if value is None:
                missing.append(key)
                continue
            if isinstance(value, str) and not value.strip():
                missing.append(key)
        if missing:
            raise PolicyError(
                f"Capability '{spec.name}' is missing required inputs: {', '.join(missing)}"
            )

    def _assert_budgets(
        self,
        *,
        run: Mapping[str, Any],
        all_actions: list[Mapping[str, Any]],
        capability_name: str,
    ) -> None:
        budgets = dict(run.get("budgets") or {})
        max_actions = _safe_int(budgets.get("max_actions"))
        if max_actions is not None:
            executed_count = sum(
                1
                for item in all_actions
                if str(item.get("status") or "").lower() == "executed"
            )
            if executed_count >= max_actions:
                raise PolicyError(
                    f"Action budget exceeded: executed={executed_count}, max_actions={max_actions}"
                )

        if capability_name == "run_variant":
            max_variant_runs = _safe_int(budgets.get("max_variant_runs"))
            if max_variant_runs is not None:
                executed_variant_runs = sum(
                    1
                    for item in all_actions
                    if str(item.get("status") or "").lower() == "executed"
                    and str(item.get("capability_name") or "") == "run_variant"
                )
                if executed_variant_runs >= max_variant_runs:
                    raise PolicyError(
                        "Variant run budget exceeded: "
                        f"executed_variant_runs={executed_variant_runs}, "
                        f"max_variant_runs={max_variant_runs}"
                    )


def _safe_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


__all__ = ["PolicyEnforcer", "PolicyError"]
