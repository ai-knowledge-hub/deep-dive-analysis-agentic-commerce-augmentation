"""Compatibility shim for goal clarification domain models.

Canonical types now live in `domain.values.types`.
"""

from __future__ import annotations

from domain.values.types import GoalClarificationState, GoalClarificationTurn


__all__ = ["GoalClarificationTurn", "GoalClarificationState"]
