from __future__ import annotations

import pytest

from domain.workflow.lifecycle import (
    TERMINAL_WORKFLOW_STATUSES,
    WorkflowStatus,
    WorkflowTransition,
    WorkflowTransitionError,
    allowed_workflow_transitions,
    can_transition_workflow,
    require_workflow_transition,
)


EXPECTED_TRANSITIONS = {
    WorkflowStatus.CREATED: {WorkflowStatus.PLANNING, WorkflowStatus.CANCELED},
    WorkflowStatus.PLANNING: {
        WorkflowStatus.PLANNED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELED,
    },
    WorkflowStatus.PLANNED: {
        WorkflowStatus.PLANNING,
        WorkflowStatus.RUNNING,
        WorkflowStatus.CANCELED,
    },
    WorkflowStatus.RUNNING: {
        WorkflowStatus.PAUSED,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELED,
    },
    WorkflowStatus.PAUSED: {
        WorkflowStatus.PLANNING,
        WorkflowStatus.RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELED,
    },
    WorkflowStatus.COMPLETED: set(),
    WorkflowStatus.FAILED: set(),
    WorkflowStatus.CANCELED: set(),
}


@pytest.mark.parametrize("source", list(WorkflowStatus))
def test_allowed_transitions_match_the_complete_contract(source: WorkflowStatus) -> None:
    assert allowed_workflow_transitions(source) == EXPECTED_TRANSITIONS[source]


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (source, target)
        for source in WorkflowStatus
        for target in WorkflowStatus
        if target in EXPECTED_TRANSITIONS[source]
    ],
)
def test_every_declared_transition_is_executable(
    source: WorkflowStatus,
    target: WorkflowStatus,
) -> None:
    assert can_transition_workflow(source, target)
    assert require_workflow_transition(source, target) == WorkflowTransition(source, target)


@pytest.mark.parametrize(
    ("source", "target"),
    [
        (source, target)
        for source in WorkflowStatus
        for target in WorkflowStatus
        if target not in EXPECTED_TRANSITIONS[source]
    ],
)
def test_every_undeclared_transition_is_rejected(
    source: WorkflowStatus,
    target: WorkflowStatus,
) -> None:
    assert not can_transition_workflow(source, target)
    with pytest.raises(WorkflowTransitionError) as error:
        require_workflow_transition(source, target)
    assert error.value.source is source
    assert error.value.target is target


def test_terminal_statuses_are_explicit_and_have_no_outgoing_transitions() -> None:
    assert TERMINAL_WORKFLOW_STATUSES == {
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELED,
    }
    assert all(not allowed_workflow_transitions(status) for status in TERMINAL_WORKFLOW_STATUSES)
