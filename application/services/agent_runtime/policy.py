from __future__ import annotations

from typing import Any, Iterable, Mapping

from application.services.agent_runtime.registry import CapabilitySpec, validate_inputs
from application.services.agent_runtime.release_policy import (
    BetaReleaseGateError,
    assert_beta_capability_available,
)


class PolicyError(ValueError):
    pass


_PROFILE_AUTO_EFFECT_CLASSES = {
    "human_approval_required": set(),
    "safe_auto": {"read", "recommend", "write_low_risk"},
    "observe": {"read", "recommend"},
}

_GOVERNED_APPROVAL_EFFECT_CLASSES = {"external_side_effect", "write_high_risk"}


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
        self._assert_beta_release_gate(spec=spec)
        self._assert_effect_class_allowed(
            run=run,
            action=action,
            effect_class=spec.effect_class,
        )
        self._assert_required_inputs(spec=spec, inputs=inputs)
        self._assert_input_schema(spec=spec, inputs=inputs)
        self._assert_budgets(
            run=run,
            all_actions=list(all_actions),
            capability_name=spec.name,
        )

    def validate_action_approval(
        self,
        *,
        run: Mapping[str, Any],
        action: Mapping[str, Any],
        spec: CapabilitySpec,
        inputs: Mapping[str, Any],
    ) -> None:
        self._assert_capability_allowed(run=run, capability_name=spec.name)
        self._assert_approval_effect_class_allowed(
            run=run,
            action=action,
            effect_class=spec.effect_class,
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

    def _assert_beta_release_gate(self, *, spec: CapabilitySpec) -> None:
        try:
            assert_beta_capability_available(
                spec.name,
                tool_id=spec.tool_id,
                effect_class=spec.effect_class,
            )
        except BetaReleaseGateError as exc:
            raise PolicyError(str(exc)) from exc

    def _assert_effect_class_allowed(
        self,
        *,
        run: Mapping[str, Any],
        action: Mapping[str, Any],
        effect_class: str,
    ) -> None:
        profile = str(run.get("policy_profile_id") or "").strip().lower()
        if not profile:
            return
        allowed = _PROFILE_AUTO_EFFECT_CLASSES.get(profile)
        if allowed is None:
            raise PolicyError(f"Unsupported policy profile '{profile}'")
        if effect_class not in allowed:
            tool_id = str(action.get("tool_id") or "").strip() or "<unknown>"
            raise PolicyError(
                f"Policy profile '{profile}' forbids auto execution of effect class '{effect_class}' for tool '{tool_id}'"
            )

    def _assert_approval_effect_class_allowed(
        self,
        *,
        run: Mapping[str, Any],
        action: Mapping[str, Any],
        effect_class: str,
    ) -> None:
        profile = str(run.get("policy_profile_id") or "").strip().lower()
        if not profile:
            return
        tool_id = str(action.get("tool_id") or "").strip() or "<unknown>"
        if profile not in _PROFILE_AUTO_EFFECT_CLASSES:
            raise PolicyError(f"Unsupported policy profile '{profile}'")
        if profile == "observe" and effect_class not in _PROFILE_AUTO_EFFECT_CLASSES["observe"]:
            raise PolicyError(
                f"Policy profile '{profile}' forbids approval of effect class '{effect_class}' for tool '{tool_id}'"
            )
        if profile in {"human_approval_required", "safe_auto"} and effect_class in _GOVERNED_APPROVAL_EFFECT_CLASSES:
            raise PolicyError(
                f"Policy profile '{profile}' requires governed approval for effect class '{effect_class}' on tool '{tool_id}'"
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

        max_cost_usd = _safe_float(budgets.get("max_cost_usd"))
        if max_cost_usd is not None:
            consumed_cost = _sum_consumed_cost_usd(all_actions)
            if consumed_cost >= max_cost_usd:
                raise PolicyError(
                    "Cost budget exceeded: "
                    f"consumed_cost_usd={consumed_cost:.4f}, "
                    f"max_cost_usd={max_cost_usd:.4f}"
                )

    def _assert_input_schema(
        self,
        *,
        spec: CapabilitySpec,
        inputs: Mapping[str, Any],
    ) -> None:
        errors = validate_inputs(spec, inputs)
        if errors:
            raise PolicyError("; ".join(errors))


def _safe_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _safe_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _sum_consumed_cost_usd(all_actions: list[Mapping[str, Any]]) -> float:
    cost_keys = {
        "cost_usd",
        "total_cost_usd",
        "validation_cost_usd",
        "estimated_cost_usd",
    }
    total = 0.0
    for action in all_actions:
        if str(action.get("status") or "").lower() != "executed":
            continue
        outputs = action.get("outputs") or {}
        total += _sum_numeric_fields(outputs, cost_keys)
    return total


def _sum_numeric_fields(value: Any, keys: set[str]) -> float:
    if isinstance(value, list):
        return sum(_sum_numeric_fields(item, keys) for item in value)
    if not isinstance(value, Mapping):
        return 0.0
    subtotal = 0.0
    for key, nested in value.items():
        if key in keys:
            number = _safe_float(nested)
            if number is not None:
                subtotal += number
        subtotal += _sum_numeric_fields(nested, keys)
    return subtotal


__all__ = ["PolicyEnforcer", "PolicyError"]
