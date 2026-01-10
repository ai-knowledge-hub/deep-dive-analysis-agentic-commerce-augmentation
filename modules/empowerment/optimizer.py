"""Simple empowerment optimizer that ranks candidate actions."""

from __future__ import annotations

from typing import List, Tuple


def rank(candidate_actions: List[str]) -> List[Tuple[str, float]]:
    """Rank candidate actions by empowerment score."""
    return [(action, 1 - idx * 0.1) for idx, action in enumerate(candidate_actions)]


__all__ = ["rank"]
