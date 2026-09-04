"""Executable registry contract for governed lab promotion."""

LAB_PROMOTION_DEFAULT_INPUTS = {
    "variant_selection": "top_1",
    "require_promote_decision": True,
    "reason": "Lab-tier promotion approved by agent runtime after policy checks.",
}

LAB_PROMOTION_INPUT_CANONICALIZERS = {
    "experiment_id": "strip",
    "variant_id": "strip_or_none",
    "variant_selection": "strip_lower_or_default",
    "reason": "strip_or_default",
}

LAB_PROMOTION_INPUT_PROPERTIES = {
    "experiment_id": {"type": "string"},
    "variant_id": {"type": "string"},
    "variant_selection": {"type": "string"},
    "require_promote_decision": {"type": "boolean"},
    "reason": {"type": "string"},
}

LAB_PROMOTION_OUTPUT_PROPERTIES = {
    "experiment_id": {"type": "string"},
    "variant_id": {"type": "string"},
    "promotion_tier": {"type": "string"},
    "reason": {"type": "string"},
    "source_metric_id": {"type": "string"},
    "posterior": {"type": "number"},
    "decision_action": {"type": "string"},
    "decision_tier": {"type": "string"},
    "decision_policy_version": {"type": "string"},
    "analytics_event_id": {"type": "string"},
    "decision_event_id": {"type": "string"},
    "status": {"type": "string"},
}

LAB_PROMOTION_OUTPUT_REQUIRED = (
    "experiment_id",
    "variant_id",
    "promotion_tier",
    "reason",
    "source_metric_id",
    "analytics_event_id",
    "decision_event_id",
    "status",
)


__all__ = [
    "LAB_PROMOTION_DEFAULT_INPUTS",
    "LAB_PROMOTION_INPUT_CANONICALIZERS",
    "LAB_PROMOTION_INPUT_PROPERTIES",
    "LAB_PROMOTION_OUTPUT_PROPERTIES",
    "LAB_PROMOTION_OUTPUT_REQUIRED",
]
