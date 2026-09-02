from __future__ import annotations

import pytest

from application.services.agent_runtime.adapters import (
    AdapterExecutionError,
    AdapterRequest,
    get_adapter_spec,
    validate_adapter_request,
)
from application.services.agent_runtime.agent_first import (
    select_skill_for_tool_id,
    skill_id_for_capability,
    skill_id_for_tool_id,
    skill_specs_for_tool_id,
)
from application.services.agent_runtime.registry import (
    capability_supported,
    default_tool_ownership_records,
    get_capability_spec,
    get_tool_spec,
    next_state_for_capability,
    recovery_template_for_capability,
    registry_contract_payload,
    tool_supported,
    validate_inputs,
    validate_outputs,
    version_context_for_capability,
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
    assert spec.owner_principal_id == "platform.commerce-optimization"
    assert spec.steward_team == "commerce-optimization"
    assert validate_inputs(spec, normalized) == []
    assert (
        "retrieval_max_results"
        in validate_inputs(
            spec, {"experiment_id": "exp-1", "retrieval_max_results": "five"}
        )[0]
    )
    assert (
        validate_outputs(spec, {"metric_id": "metric-1", "variant_id": "variant-1"})
        == []
    )
    assert (
        "metric_id"
        in validate_outputs(spec, {"metric_id": 123, "variant_id": "variant-1"})[0]
    )
    assert "variant_id" in validate_outputs(spec, {"metric_id": "metric-1"})[0]
    assert "metric_id" in validate_outputs(spec, {"variant_id": "variant-1"})[0]
    baseline = get_capability_spec("run_control_baseline")
    assert baseline is not None
    assert set(baseline.output_schema["required"]) == {"metric_id", "variant_id"}
    posterior = get_capability_spec("update_posterior_and_decisions")
    assert posterior is not None
    assert set(posterior.output_schema["required"]) == {"new_metric_id", "variant_id"}
    assert (
        validate_outputs(
            posterior,
            {
                "new_metric_id": "metric-2",
                "source_metric_id": "metric-1",
                "variant_id": "variant-1",
            },
        )
        == []
    )
    version_context = version_context_for_capability(
        "run_variant",
        tool_id="experiment.run_variant",
        skill_id="optimize-product-representation",
    )
    assert version_context["registry_version"] == "agent-runtime-static-v1"
    assert len(str(version_context["registry_fingerprint"])) == 64
    assert version_context["tool_version"] == "v1"
    assert version_context["skill_version"] == "v1"
    validation_template = recovery_template_for_capability(
        "request_synthetic_validation"
    )
    assert validation_template is not None
    assert validation_template["default_inputs"]["auto_run"] is False


def test_registry_support_and_next_state():
    assert capability_supported("seed_hypotheses") is True
    assert capability_supported("check_protocol_readiness") is True
    assert capability_supported("not_real") is False
    assert next_state_for_capability("seed_hypotheses") == "hypotheses_ready"
    assert next_state_for_capability("recommend_next_action") is None


def test_synthetic_validation_registry_canonicalizes_every_executable_string():
    spec = get_capability_spec("request_synthetic_validation")
    assert spec is not None
    normalized = spec.normalize_inputs(
        {
            "experiment_id": " experiment-a ",
            "provider": " OPENROUTER ",
            "mode": " IN_APP_BYOK ",
            "model": " approved-model ",
            "prompt_version": " v1 ",
            "variant_id": " variant-a ",
            "variant_selection": " TOP_1 ",
            "auto_run": False,
        }
    )

    assert normalized == {
        "experiment_id": "experiment-a",
        "provider": "openrouter",
        "mode": "in_app_byok",
        "model": "approved-model",
        "prompt_version": "v1",
        "variant_id": "variant-a",
        "variant_selection": "top_1",
        "auto_run": False,
    }
    assert spec.normalize_inputs(normalized) == normalized
    assert spec.input_schema["properties"]["model"] == {"type": "string"}


def test_tool_registry_shim_contains_machine_facing_ids():
    tool = get_tool_spec("experiment.run_variant")
    assert tool is not None
    assert tool.capability_name == "run_variant"
    assert tool.effect_class == "write_low_risk"
    assert tool.owner_principal_id == "platform.commerce-optimization"
    normalized = tool.normalize_inputs({"experiment_id": "exp-1"})
    assert normalized["variant_selection"] == "top_1"
    assert normalized["retrieval_max_results"] == 5
    assert tool_supported("experiment.run_variant") is True
    protocol_tool = get_tool_spec("protocol.readiness_check")
    assert protocol_tool is not None
    assert protocol_tool.capability_name == "check_protocol_readiness"
    assert protocol_tool.effect_class == "read"
    assert protocol_tool.output_schema["properties"]["receipt_id"]["type"] == "string"
    discovery_tool = get_tool_spec("protocol.discover_candidates")
    assert discovery_tool is not None
    assert discovery_tool.capability_name == "discover_protocol_candidates"
    assert discovery_tool.effect_class == "read"
    assert discovery_tool.output_schema["properties"]["candidates"]["type"] == "array"
    assert tool_supported("not.real") is False


def test_registry_payload_can_use_persistent_tool_ownership():
    payload = registry_contract_payload(
        ownership_by_tool=[
            {
                "tool_id": "experiment.run_variant",
                "owner_principal_id": "principal.registry-owner",
                "steward_team": "registry-stewards",
                "source": "registry_test",
            }
        ]
    )
    tool = next(
        item for item in payload["tools"] if item["id"] == "experiment.run_variant"
    )
    capability = next(
        item for item in payload["capabilities"] if item["name"] == "run_variant"
    )
    assert payload["registry_ownership_source"] == "persistent"
    adapter = next(
        item
        for item in payload["execution_adapters"]
        if item["id"] == "protocol.readiness.v1"
    )
    assert adapter["permission_scope"] == "protocol.readiness:read"
    assert adapter["effect_class"] == "read"
    assert adapter["external_side_effects"] is False
    discovery_adapter = next(
        item
        for item in payload["execution_adapters"]
        if item["id"] == "protocol.discovery.v1"
    )
    planned_checkout_adapter = next(
        item
        for item in payload["execution_adapters"]
        if item["id"] == "protocol.checkout.v1"
    )
    assert discovery_adapter["permission_scope"] == "protocol.discovery:read"
    assert discovery_adapter["allowed_capabilities"] == ["discover_protocol_candidates"]
    assert planned_checkout_adapter["status"] == "planned"
    assert planned_checkout_adapter["effect_class"] == "external_side_effect"
    assert planned_checkout_adapter["allowed_capabilities"] == []
    assert planned_checkout_adapter["writes_external_system"] is True
    assert planned_checkout_adapter["requires_operator_review"] is True
    assert planned_checkout_adapter["contract_intent"] == "readiness_boundary"
    assert (
        "Real transaction execution is not supported"
        in planned_checkout_adapter["description"]
    )
    assert planned_checkout_adapter["receipt_contract"]["required"] is True
    assert (
        planned_checkout_adapter["receipt_contract"]["receipt_type"]
        == "external_write_execution"
    )
    assert (
        "approval_receipt_id"
        in planned_checkout_adapter["receipt_contract"]["required_fields"]
    )
    assert (
        "checkout_session_id"
        in planned_checkout_adapter["receipt_contract"]["evidence_fields"]
    )
    assert planned_checkout_adapter["receipt_contract"]["must_link_run_event"] is True
    planned_payment_adapter = next(
        item
        for item in payload["execution_adapters"]
        if item["id"] == "protocol.payment_delegation.v1"
    )
    planned_browser_adapter = next(
        item
        for item in payload["execution_adapters"]
        if item["id"] == "fallback.browser_checkout.v1"
    )
    assert (
        planned_payment_adapter["receipt_contract"]["receipt_type"]
        == "external_write_execution"
    )
    assert planned_payment_adapter["contract_intent"] == "readiness_boundary"
    assert (
        "payment_handler"
        in planned_payment_adapter["receipt_contract"]["evidence_fields"]
    )
    assert (
        planned_browser_adapter["receipt_contract"]["receipt_type"]
        == "external_write_execution"
    )
    assert planned_browser_adapter["contract_intent"] == "readiness_boundary"
    assert (
        "browser_session_id"
        in planned_browser_adapter["receipt_contract"]["evidence_fields"]
    )
    assert any(
        item["id"] == "buyer-assistant-v1"
        and item["default_harness_id"] == "safe_autonomy_b2b"
        for item in payload["agent_profile_defaults"]
    )
    assert payload["skill_ids_by_executable_tool"]["experiment.run_variant"] == [
        "optimize-product-representation"
    ]
    assert "run.read" in payload["declared_non_executable_skill_tools"]
    assert "protocol.ucp.checkout" in payload["declared_non_executable_skill_tools"]
    assert "protocol.acp.checkout" in payload["declared_non_executable_skill_tools"]
    assert "protocol.payment.delegate" in payload["declared_non_executable_skill_tools"]
    assert "browser.checkout_fallback" in payload["declared_non_executable_skill_tools"]
    readiness_boundaries = {
        item["tool_id"]: item for item in payload["readiness_boundaries"]
    }
    assert set(readiness_boundaries) == {
        "browser.checkout_fallback",
        "protocol.acp.checkout",
        "protocol.payment.delegate",
        "protocol.ucp.checkout",
    }
    assert readiness_boundaries["protocol.ucp.checkout"]["adapter_id"] == (
        "protocol.checkout.v1"
    )
    assert readiness_boundaries["protocol.ucp.checkout"]["contract_intent"] == (
        "readiness_boundary"
    )
    assert readiness_boundaries["protocol.ucp.checkout"]["executable"] is False
    assert readiness_boundaries["protocol.ucp.checkout"]["skill_ids"] == [
        "execute-governed-protocol-commerce"
    ]
    assert readiness_boundaries["protocol.ucp.checkout"]["blocked_reason"] == (
        "readiness_boundary_only_no_transaction_execution"
    )
    assert (
        next(
            item
            for item in payload["skill_tool_mappings"]
            if item["tool_id"] == "run.read"
        )["executable"]
        is False
    )
    assert (
        next(
            item
            for item in payload["skill_tool_mappings"]
            if item["tool_id"] == "protocol.ucp.checkout"
        )["executable"]
        is False
    )
    ucp_checkout_mapping = next(
        item
        for item in payload["skill_tool_mappings"]
        if item["tool_id"] == "protocol.ucp.checkout"
    )
    assert ucp_checkout_mapping["adapter_id"] == "protocol.checkout.v1"
    assert ucp_checkout_mapping["contract_intent"] == "readiness_boundary"
    assert (
        ucp_checkout_mapping["blocked_reason"]
        == "readiness_boundary_only_no_transaction_execution"
    )
    assert (
        ucp_checkout_mapping["receipt_contract"]["receipt_type"]
        == "external_write_execution"
    )
    assert tool["executable"] is True
    assert tool["external_agent_contract"]["minimal_request"] == {
        "tool_id": "experiment.run_variant",
        "plan_mode": "single_tool",
    }
    assert tool["external_agent_contract"]["required_scopes"]["tool"] == [
        "tool:experiment.run_variant",
        "tools:*",
    ]
    template = next(
        item
        for item in payload["recovery_templates"]
        if item["capability_name"] == "request_synthetic_validation"
    )
    assert template["id"] == "recovery.request_synthetic_validation"
    assert template["default_inputs"]["auto_run"] is False
    assert tool["owner_principal_id"] == "principal.registry-owner"
    assert tool["steward_team"] == "registry-stewards"
    assert tool["ownership_source"] == "registry_test"
    assert capability["owner_principal_id"] == "principal.registry-owner"
    assert capability["steward_team"] == "registry-stewards"
    assert any(
        item["tool_id"] == "experiment.run_variant"
        for item in default_tool_ownership_records()
    )


def test_adapter_registry_rejects_capability_mismatch():
    spec = get_adapter_spec("protocol.readiness.v1")
    assert spec is not None
    valid = validate_adapter_request(
        request=AdapterRequest(
            adapter_id="protocol.readiness.v1",
            channel_type="protocol",
            capability_name="check_protocol_readiness",
            client_id="client-a",
            user_id=None,
            inputs={"product_id": "product-a"},
        )
    )
    assert valid.permission_scope == "protocol.readiness:read"

    with pytest.raises(AdapterExecutionError, match="cannot execute capability"):
        validate_adapter_request(
            request=AdapterRequest(
                adapter_id="protocol.readiness.v1",
                channel_type="protocol",
                capability_name="request_synthetic_validation",
                client_id="client-a",
                user_id=None,
                inputs={},
            )
        )


def test_runtime_tools_resolve_to_skill_lineage():
    assert skill_id_for_tool_id("protocol.readiness_check") == (
        "discover-protocol-candidates"
    )
    assert skill_id_for_tool_id("protocol.discover_candidates") == (
        "discover-protocol-candidates"
    )
    assert (
        skill_id_for_tool_id("experiment.run_variant")
        == "optimize-product-representation"
    )
    assert (
        skill_id_for_capability("request_synthetic_validation")
        == "request-validation-and-ingest-result"
    )
    review_candidates = skill_specs_for_tool_id("validation.review_readiness")
    assert [skill.id for skill in review_candidates] == [
        "request-validation-and-ingest-result",
        "promote-and-publish-approved-copy",
    ]
    assert skill_id_for_tool_id("validation.review_readiness") == (
        "request-validation-and-ingest-result"
    )
    assert (
        skill_id_for_tool_id(
            "validation.review_readiness",
            allowed_skill_ids={"promote-and-publish-approved-copy"},
        )
        == "promote-and-publish-approved-copy"
    )
    assert (
        select_skill_for_tool_id(
            "validation.review_readiness",
            preferred_skill_id="promote-and-publish-approved-copy",
        ).id
        == "promote-and-publish-approved-copy"
    )
    assert (
        skill_id_for_tool_id("copy.publish_revision")
        == "promote-and-publish-approved-copy"
    )
    assert skill_id_for_tool_id("not.real") is None
