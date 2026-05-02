from __future__ import annotations

from application.services.agent_runtime.registry import (
    capability_supported,
    get_capability_spec,
    get_tool_spec,
    next_state_for_capability,
    tool_supported,
    validate_inputs,
    validate_outputs,
    version_context_for_capability,
)
from application.services.agent_runtime.agent_first import (
    skill_id_for_capability,
    skill_id_for_tool_id,
)


def test_registry_contains_core_capability_and_defaults():
    spec = get_capability_spec("run_variant")
    assert spec is not None
    normalized = spec.normalize_inputs({"experiment_id": "exp-1"})
    assert normalized["variant_selection"] == "top_1"
    assert normalized["retrieval_max_results"] == 5
    assert normalized["experiment_id"] == "exp-1"
    assert spec.summary
    assert spec.input_schema["properties"]["experiment_id"]["type"] == "string"
    assert spec.output_schema["properties"]["metric_id"]["type"] == "string"
    assert spec.review_checklist
    assert validate_inputs(spec, normalized) == []
    assert "retrieval_max_results" in validate_inputs(
        spec, {"experiment_id": "exp-1", "retrieval_max_results": "five"}
    )[0]
    assert validate_outputs(spec, {"metric_id": "metric-1"}) == []
    assert "metric_id" in validate_outputs(spec, {"metric_id": 123})[0]
    assert version_context_for_capability(
        "run_variant",
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
    ) == {
        "registry_version": "agent-runtime-static-v1",
        "tool_version": "v1",
        "skill_version": "v1",
    }


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


def test_runtime_tools_resolve_to_skill_lineage():
    assert skill_id_for_tool_id("experiment.run_variant") == "optimize-product-representation"
    assert (
        skill_id_for_capability("request_synthetic_validation")
        == "request-validation-and-ingest-result"
    )
    assert skill_id_for_tool_id("copy.publish_revision") == "promote-and-publish-approved-copy"
    assert skill_id_for_tool_id("not.real") is None
