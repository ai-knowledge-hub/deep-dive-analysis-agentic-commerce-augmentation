from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class ProposedAction:
    capability_name: str
    capability_version: Optional[str]
    inputs: Dict[str, Any]
    rationale: str
    confidence: float = 0.65

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def build_initial_plan(
    *,
    experiment_id: Optional[str],
    allowed_capabilities: List[str],
    capability_versions: Dict[str, Any],
    objective: Optional[Dict[str, Any]] = None,
) -> List[ProposedAction]:
    """
    Minimal v0 planner.

    - Produces a small, human-reviewable action queue.
    - Does not execute anything (execution is handled by AgentRuntime later).
    """
    allowed = {str(x).strip() for x in allowed_capabilities if str(x).strip()}
    versions = capability_versions or {}
    objective = objective or {}

    def v(name: str) -> Optional[str]:
        value = versions.get(name)
        return str(value) if isinstance(value, str) and value.strip() else None

    actions: List[ProposedAction] = []
    if experiment_id:
        base_inputs = {"experiment_id": experiment_id}
    else:
        base_inputs = {}

    protocol_discovery_inputs = _protocol_discovery_inputs(objective)

    if "freeze_retrieval_protocol" in allowed:
        actions.append(
            ProposedAction(
                capability_name="freeze_retrieval_protocol",
                capability_version=v("freeze_retrieval_protocol"),
                inputs={**base_inputs, "retrieval_max_results": 5},
                rationale="Freeze a retrieval snapshot set so variant comparisons are fair and time-drift resistant.",
                confidence=0.7,
            )
        )
    if "run_control_baseline" in allowed:
        actions.append(
            ProposedAction(
                capability_name="run_control_baseline",
                capability_version=v("run_control_baseline"),
                inputs=base_inputs,
                rationale="Score the control baseline on the frozen snapshot to unlock candidate runs (baseline-first gating).",
                confidence=0.7,
            )
        )
    if "seed_hypotheses" in allowed:
        actions.append(
            ProposedAction(
                capability_name="seed_hypotheses",
                capability_version=v("seed_hypotheses"),
                inputs=base_inputs,
                rationale="Derive and persist initial hypotheses from baseline deltas (missing winner signals).",
                confidence=0.65,
            )
        )
    if "generate_variants" in allowed:
        actions.append(
            ProposedAction(
                capability_name="generate_variants",
                capability_version=v("generate_variants"),
                inputs={
                    **base_inputs,
                    "mode": "loop_evidence",
                    "strategy": "both",
                    "max_candidates": 3,
                    "persist_count": 2,
                },
                rationale="Generate candidate variants linked to hypotheses (draft only until reviewed).",
                confidence=0.6,
            )
        )
    if "run_variant" in allowed:
        actions.append(
            ProposedAction(
                capability_name="run_variant",
                capability_version=v("run_variant"),
                inputs={**base_inputs, "variant_selection": "top_1"},
                rationale="Run a single candidate to collect early signal within budget (requires baseline gate).",
                confidence=0.55,
            )
        )
    if "discover_protocol_candidates" in allowed and protocol_discovery_inputs:
        actions.append(
            ProposedAction(
                capability_name="discover_protocol_candidates",
                capability_version=v("discover_protocol_candidates"),
                inputs=protocol_discovery_inputs,
                rationale=(
                    "Discover read-only ACP/UCP candidates and summarize "
                    "merchant protocol readiness evidence."
                ),
                confidence=0.6,
            )
        )
    if "request_synthetic_validation" in allowed:
        actions.append(
            ProposedAction(
                capability_name="request_synthetic_validation",
                capability_version=v("request_synthetic_validation"),
                inputs={
                    **base_inputs,
                    "provider": "openrouter",
                    "mode": "in_app_byok",
                    "auto_run": True,
                    "variant_selection": "top_1",
                    "prompt_version": "v1",
                },
                rationale="Request synthetic validation jobs for the latest candidate to increase evidence reliability.",
                confidence=0.55,
            )
        )
    if "review_validation_readiness" in allowed:
        actions.append(
            ProposedAction(
                capability_name="review_validation_readiness",
                capability_version=v("review_validation_readiness"),
                inputs={
                    **base_inputs,
                    "variant_selection": "top_1",
                    "prod_min_coverage": 0.2,
                    "min_verified_runs": 3,
                    "min_synthetic_results": 1,
                },
                rationale="Review observed and synthetic validation gates before promotion decisions.",
                confidence=0.6,
            )
        )
    if "update_posterior_and_decisions" in allowed:
        actions.append(
            ProposedAction(
                capability_name="update_posterior_and_decisions",
                capability_version=v("update_posterior_and_decisions"),
                inputs=base_inputs,
                rationale="Compute posterior and decision outputs from combined experiment/synthetic/observed evidence.",
                confidence=0.6,
            )
        )
    if "recommend_next_action" in allowed:
        actions.append(
            ProposedAction(
                capability_name="recommend_next_action",
                capability_version=v("recommend_next_action"),
                inputs=base_inputs,
                rationale="Generate a constrained next-step recommendation from experiment outcomes, validation state, and policy context.",
                confidence=0.6,
            )
        )
    if "promote_variant_lab" in allowed:
        actions.append(
            ProposedAction(
                capability_name="promote_variant_lab",
                capability_version=v("promote_variant_lab"),
                inputs={
                    **base_inputs,
                    "variant_selection": "top_1",
                    "require_promote_decision": True,
                },
                rationale="Promote a candidate to lab tier when policy outputs indicate promote (without triggering prod/publish paths).",
                confidence=0.55,
            )
        )
    if "promote_variant_prod" in allowed:
        actions.append(
            ProposedAction(
                capability_name="promote_variant_prod",
                capability_version=v("promote_variant_prod"),
                inputs={
                    **base_inputs,
                    "variant_selection": "top_1",
                    "require_promote_decision": True,
                    "prod_min_coverage": 0.2,
                    "min_verified_runs": 3,
                    "min_synthetic_results": 1,
                },
                rationale="Promote a candidate to prod tier only when observed-readiness gates pass and decision policy indicates promotion.",
                confidence=0.5,
            )
        )
    if "publish_copy_revision" in allowed:
        actions.append(
            ProposedAction(
                capability_name="publish_copy_revision",
                capability_version=v("publish_copy_revision"),
                inputs={
                    **base_inputs,
                    "variant_selection": "top_1",
                    "require_prod_promotion": True,
                },
                rationale="Publish copy revision from a prod-promoted variant into product description, with auditable events.",
                confidence=0.45,
            )
        )
    return actions


def _protocol_discovery_inputs(objective: Dict[str, Any]) -> Dict[str, Any]:
    query = _first_non_empty(
        objective.get("query"),
        objective.get("search_query"),
        objective.get("product_query"),
    )
    if not query:
        return {}
    inputs: Dict[str, Any] = {"query": query, "limit": _safe_limit(objective.get("limit"))}
    brand_id = _first_non_empty(objective.get("brand_id"))
    if brand_id:
        inputs["brand_id"] = brand_id
    protocol = _first_non_empty(objective.get("protocol"))
    if protocol in {"ucp", "acp"}:
        inputs["protocol"] = protocol
    inferred_intent = objective.get("inferred_intent")
    if isinstance(inferred_intent, dict):
        inputs["inferred_intent"] = inferred_intent
    return inputs


def _first_non_empty(*values: Any) -> str | None:
    for value in values:
        parsed = str(value or "").strip()
        if parsed:
            return parsed
    return None


def _safe_limit(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 10
    return max(1, min(parsed, 50))


__all__ = ["ProposedAction", "build_initial_plan"]
