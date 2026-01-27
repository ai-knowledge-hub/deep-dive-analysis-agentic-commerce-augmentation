"""Pure conversation context types and formatting helpers.

This module contains no DB/LLM calls and no SessionManager dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


@dataclass
class ContextPacket:
    """A packet of context information for LLM prompts."""

    session_id: str
    user_id: str
    goals: List[str]
    semantic_goals: List[str]
    turns: List[Dict[str, Any]]
    latest_episode: Dict[str, Any] | None
    metadata: Dict[str, Any]

    def messages(self, system_instruction: str | None = None) -> List[dict[str, str]]:
        messages: List[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        for turn in self.turns:
            messages.append({"role": turn["speaker"], "content": turn["content"]})
        return messages


def format_turns(turns: Sequence[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for turn in turns:
        speaker = turn.get("speaker", "user")
        content = turn.get("content", "")
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def default_metadata(packet: ContextPacket) -> Dict[str, Any]:
    return {
        "session_id": packet.session_id,
        "user_id": packet.user_id,
        "goals": packet.goals,
        "semantic_goals": packet.semantic_goals,
        "latest_episode": packet.latest_episode,
    }


def render_context(packet: ContextPacket, include_turns: int = 6) -> str:
    explicit_goals = ", ".join(packet.goals) if packet.goals else "None captured"
    semantic = (
        ", ".join(packet.semantic_goals) if packet.semantic_goals else "None recorded"
    )
    latest_episode = packet.latest_episode or {}
    episode_text = (
        latest_episode.get("takeaways")
        or latest_episode.get("outcome")
        or "No outcomes yet"
    )

    metadata_lines = [
        f"- {key}: {value}"
        for key, value in (packet.metadata or {}).items()
        if key not in {"clarification_state"}
    ]
    metadata_text = (
        "\n".join(metadata_lines) if metadata_lines else "(no state metadata)"
    )

    recent_turns = format_turns(packet.turns[-include_turns:]) or "(no prior turns)"

    return (
        f"Session ID: {packet.session_id}\n"
        f"User ID: {packet.user_id}\n"
        f"Explicit goals: {explicit_goals}\n"
        f"Semantic goals: {semantic}\n"
        f"Latest outcome note: {episode_text}\n"
        f"State metadata:\n{metadata_text}\n"
        f"Recent conversation:\n{recent_turns}"
    )


__all__ = ["ContextPacket", "default_metadata", "format_turns", "render_context"]

