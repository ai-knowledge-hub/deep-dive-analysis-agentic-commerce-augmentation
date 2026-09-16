"""Closed compatibility action lifecycle used by completion governance."""

from __future__ import annotations


ACTION_STATUSES = frozenset(
    {"proposed", "approved", "rejected", "executing", "executed", "failed"}
)
COMPLETION_COMPATIBLE_ACTION_STATUSES = frozenset({"executed", "rejected"})


def is_action_status(value: object) -> bool:
    return type(value) is str and value in ACTION_STATUSES


def is_completion_compatible_action_status(value: object) -> bool:
    return type(value) is str and value in COMPLETION_COMPATIBLE_ACTION_STATUSES


__all__ = [
    "ACTION_STATUSES",
    "COMPLETION_COMPATIBLE_ACTION_STATUSES",
    "is_action_status",
    "is_completion_compatible_action_status",
]
