"""Pure workflow lifecycle rules shared by future orchestration adapters.

The contract is intentionally independent of persistence, queues, and workflow
frameworks. State changes must pass through this module before an adapter emits
an event or updates a projection.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Final, Mapping


class WorkflowStatus(str, Enum):
    """Canonical states for the top-level workflow lifecycle."""

    CREATED = "created"
    PLANNING = "planning"
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


TERMINAL_WORKFLOW_STATUSES: Final[frozenset[WorkflowStatus]] = frozenset(
    {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELED,
    }
)

_ALLOWED_WORKFLOW_TRANSITIONS: Final[
    Mapping[WorkflowStatus, frozenset[WorkflowStatus]]
] = MappingProxyType(
    {
        WorkflowStatus.CREATED: frozenset(
            {WorkflowStatus.PLANNING, WorkflowStatus.CANCELED}
        ),
        WorkflowStatus.PLANNING: frozenset(
            {
                WorkflowStatus.PLANNED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELED,
            }
        ),
        WorkflowStatus.PLANNED: frozenset(
            {
                WorkflowStatus.PLANNING,
                WorkflowStatus.RUNNING,
                WorkflowStatus.CANCELED,
            }
        ),
        WorkflowStatus.RUNNING: frozenset(
            {
                WorkflowStatus.PAUSED,
                WorkflowStatus.COMPLETED,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELED,
            }
        ),
        WorkflowStatus.PAUSED: frozenset(
            {
                WorkflowStatus.PLANNING,
                WorkflowStatus.RUNNING,
                WorkflowStatus.FAILED,
                WorkflowStatus.CANCELED,
            }
        ),
        WorkflowStatus.COMPLETED: frozenset(),
        WorkflowStatus.FAILED: frozenset(),
        WorkflowStatus.CANCELED: frozenset(),
    }
)


class WorkflowTransitionError(ValueError):
    """Raised when a workflow state change violates the lifecycle contract."""

    def __init__(self, source: WorkflowStatus, target: WorkflowStatus) -> None:
        self.source = source
        self.target = target
        super().__init__(f"Workflow cannot transition from {source.value} to {target.value}")


@dataclass(frozen=True)
class WorkflowTransition:
    """A validated workflow state change suitable for event creation."""

    source: WorkflowStatus
    target: WorkflowStatus


def allowed_workflow_transitions(status: WorkflowStatus) -> frozenset[WorkflowStatus]:
    """Return the immutable set of states reachable from ``status``."""

    return _ALLOWED_WORKFLOW_TRANSITIONS[status]


def can_transition_workflow(source: WorkflowStatus, target: WorkflowStatus) -> bool:
    """Return whether ``source -> target`` is an allowed state change."""

    return target in allowed_workflow_transitions(source)


def require_workflow_transition(
    source: WorkflowStatus,
    target: WorkflowStatus,
) -> WorkflowTransition:
    """Validate and return a transition, or raise a domain-specific error."""

    if not can_transition_workflow(source, target):
        raise WorkflowTransitionError(source, target)
    return WorkflowTransition(source=source, target=target)
