"""Immutable security release and mitigation requirements for schema v1."""

BLOCKING_DISPOSITION = "excluded_until_required_controls_implemented"

CAPABILITY_RELEASE_GATES = {
    "autonomous_production_publishing": frozenset({"SEC-06", "SEC-16"}),
    "automatic_global_harness_promotion": frozenset({"SEC-12"}),
    "expanded_connectors_without_secret_egress_ssrf_controls": frozenset(
        {"SEC-13", "SEC-14", "SEC-19"}
    ),
    "expanded_production_telemetry_and_parallel_context_logging": frozenset(
        {"SEC-09", "SEC-13", "SEC-18", "SEC-19"}
    ),
    "parallel_multi_tenant_worker_execution": frozenset(
        {"SEC-09", "SEC-16", "SEC-19", "SEC-20"}
    ),
    "public_durable_workflow_and_peer_messages": frozenset(
        {"SEC-07", "SEC-08", "SEC-18", "SEC-20"}
    ),
    "unreviewed_memory_promotion": frozenset({"SEC-11"}),
    "write_capable_dynamic_child_delegation": frozenset({"SEC-06", "SEC-16"}),
}

SCHEMA_REQUIRED_CAPABILITY_EXCLUSIONS = {
    "1.0": {
        "THR-01": frozenset(
            {"automatic_global_harness_promotion", "unreviewed_memory_promotion"}
        ),
        "THR-02": frozenset(
            {
                "autonomous_production_publishing",
                "write_capable_dynamic_child_delegation",
            }
        ),
        "THR-04": frozenset({"public_durable_workflow_and_peer_messages"}),
        "THR-05": frozenset({"parallel_multi_tenant_worker_execution"}),
        "THR-10": frozenset(
            {"expanded_connectors_without_secret_egress_ssrf_controls"}
        ),
        "THR-16": frozenset(
            {"expanded_production_telemetry_and_parallel_context_logging"}
        ),
    }
}

SCHEMA_REQUIRED_MITIGATION_CLOSURES = {
    "1.0": {
        "THR-01": {
            "control_ids": frozenset(
                {"SEC-02", "SEC-09", "SEC-10", "SEC-11", "SEC-12"}
            ),
            "verification_ids": frozenset(
                {"SVT-02", "SVT-09", "SVT-10", "SVT-11", "SVT-12"}
            ),
        },
        "THR-02": {
            "control_ids": frozenset(
                {"SEC-01", "SEC-02", "SEC-06", "SEC-09", "SEC-16"}
            ),
            "verification_ids": frozenset(
                {"SVT-01", "SVT-02", "SVT-06", "SVT-09", "SVT-16"}
            ),
        },
        "THR-04": {
            "control_ids": frozenset(
                {
                    "SEC-03",
                    "SEC-04",
                    "SEC-05",
                    "SEC-07",
                    "SEC-08",
                    "SEC-18",
                    "SEC-20",
                }
            ),
            "verification_ids": frozenset(
                {
                    "SVT-03",
                    "SVT-04",
                    "SVT-05",
                    "SVT-07",
                    "SVT-08",
                    "SVT-18",
                    "SVT-20",
                }
            ),
        },
        "THR-05": {
            "control_ids": frozenset(
                {
                    "SEC-01",
                    "SEC-03",
                    "SEC-09",
                    "SEC-13",
                    "SEC-16",
                    "SEC-19",
                    "SEC-20",
                }
            ),
            "verification_ids": frozenset(
                {
                    "SVT-01",
                    "SVT-03",
                    "SVT-09",
                    "SVT-13",
                    "SVT-16",
                    "SVT-19",
                    "SVT-20",
                }
            ),
        },
        "THR-10": {
            "control_ids": frozenset(
                {"SEC-01", "SEC-09", "SEC-13", "SEC-14", "SEC-19"}
            ),
            "verification_ids": frozenset(
                {"SVT-01", "SVT-09", "SVT-13", "SVT-14", "SVT-19"}
            ),
        },
        "THR-16": {
            "control_ids": frozenset(
                {"SEC-09", "SEC-13", "SEC-18", "SEC-19", "SEC-20"}
            ),
            "verification_ids": frozenset(
                {"SVT-09", "SVT-13", "SVT-18", "SVT-19", "SVT-20"}
            ),
        },
    }
}

SCHEMA_CLOSURE_APPROVER_IDS = {
    "1.0": frozenset({"security-review-board"}),
}

__all__ = [
    "BLOCKING_DISPOSITION",
    "CAPABILITY_RELEASE_GATES",
    "SCHEMA_CLOSURE_APPROVER_IDS",
    "SCHEMA_REQUIRED_CAPABILITY_EXCLUSIONS",
    "SCHEMA_REQUIRED_MITIGATION_CLOSURES",
]
