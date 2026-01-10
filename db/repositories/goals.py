"""Backward compatibility: re-exports from modules.memory.repositories.goals."""

from modules.memory.repositories.goals import (
    create_goal,
    delete_goal,
    get_goal,
    list_goals,
    list_goals_for_session,
)

__all__ = [
    "create_goal",
    "delete_goal",
    "get_goal",
    "list_goals",
    "list_goals_for_session",
]
