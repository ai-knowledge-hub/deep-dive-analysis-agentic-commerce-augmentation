"""Domain contracts for durable workflow orchestration."""

from domain.workflow.lifecycle import (
    TERMINAL_WORKFLOW_STATUSES,
    WorkflowStatus,
    WorkflowTransition,
    WorkflowTransitionError,
    allowed_workflow_transitions,
    can_transition_workflow,
    require_workflow_transition,
)

__all__ = [
    "TERMINAL_WORKFLOW_STATUSES",
    "WorkflowStatus",
    "WorkflowTransition",
    "WorkflowTransitionError",
    "allowed_workflow_transitions",
    "can_transition_workflow",
    "require_workflow_transition",
]
