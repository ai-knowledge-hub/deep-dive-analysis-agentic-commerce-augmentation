"""Pure helpers for extracting goals and determining readiness."""

from __future__ import annotations

from typing import List

from domain.values.types import GoalClarificationState


def has_summary(agent_response: str) -> bool:
    lowered = agent_response.lower()
    summary_phrases = [
        "does that capture",
        "does that sound",
        "is that accurate",
        "is this accurate",
        "let me confirm",
        "to confirm",
        "here's what i'm hearing",
        "here is what i'm hearing",
        "recap",
        "summary",
    ]
    if any(phrase in lowered for phrase in summary_phrases):
        return True
    list_lines = [
        line
        for line in agent_response.splitlines()
        if line.strip().startswith(("-", "*")) or line.strip()[:2].isdigit()
    ]
    return len(list_lines) >= 2


def extract_goals(agent_response: str) -> List[str]:
    """Extract goals from an agent response (heuristic)."""
    goals: List[str] = []
    for line in agent_response.splitlines():
        raw = line.strip()
        if not raw:
            continue
        if raw.startswith(("-", "*")):
            candidate = raw.lstrip("-* ").strip()
            if candidate:
                goals.append(candidate)
            continue
        if raw[0].isdigit() and "." in raw[:3]:
            candidate = raw.split(".", 1)[1].strip()
            if candidate:
                goals.append(candidate)
            continue
        lowered = raw.lower()
        for prefix in ("goal:", "constraint:", "success:", "need:", "needs:"):
            if lowered.startswith(prefix):
                goals.append(raw.split(":", 1)[1].strip())
                break
    return goals or [agent_response.strip()]


def fallback_goals(state: GoalClarificationState) -> List[str]:
    candidates: List[str] = []
    if state.query:
        candidates.append(state.query.strip())
    user_turns = [turn.content for turn in state.turns if turn.speaker == "user"]
    if user_turns:
        candidates.append(user_turns[-1].strip())
    return [candidate for candidate in candidates if candidate]


__all__ = ["extract_goals", "fallback_goals", "has_summary"]

