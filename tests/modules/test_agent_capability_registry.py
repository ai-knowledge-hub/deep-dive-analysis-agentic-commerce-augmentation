from __future__ import annotations

from application.services.agent_runtime.registry import (
    capability_supported,
    get_capability_spec,
    get_tool_spec,
    next_state_for_capability,
    tool_supported,
)


def test_registry_contains_core_capability_and_defaults():
    spec = get_capability_spec("run_variant")
    assert spec is not None
    normalized = spec.normalize_inputs({"experiment_id": "exp-1"})
    assert normalized["variant_selection"] == "top_1"
    assert normalized["retrieval_max_results"] == 5
    assert normalized["experiment_id"] == "exp-1"


def test_registry_support_and_next_state():
    assert capability_supported("seed_hypotheses") is True
    assert capability_supported("not_real") is False
    assert next_state_for_capability("seed_hypotheses") == "hypotheses_ready"
    assert next_state_for_capability("recommend_next_action") is None


def test_tool_registry_shim_contains_machine_facing_ids():
    tool = get_tool_spec("experiment.run_variant")
    assert tool is not None
    assert tool.capability_name == "run_variant"
    assert tool.effect_class == "write_low_risk"
    normalized = tool.normalize_inputs({"experiment_id": "exp-1"})
    assert normalized["variant_selection"] == "top_1"
    assert normalized["retrieval_max_results"] == 5
    assert tool_supported("experiment.run_variant") is True
    assert tool_supported("not.real") is False
