"""Shared helpers for building LLM prompt context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, Tuple

from modules.memory.session_manager import SessionManager

if TYPE_CHECKING:  # pragma: no cover - imported for type hints only
    from modules.values.domain import ClarificationState


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
        """Build a message list for LLM chat."""
        messages: List[dict[str, str]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})

        for turn in self.turns:
            messages.append({"role": turn["speaker"], "content": turn["content"]})
        return messages


def build_context(
    manager: SessionManager,
    include_turns: int = 8,
    extra_metadata: Dict[str, Any] | None = None,
) -> ContextPacket:
    """Build a context packet from session manager."""
    snapshot = manager.summary(include_turn_limit=include_turns)
    turns = snapshot.turns[-include_turns:]
    metadata = dict(manager.get_state())
    if extra_metadata:
        metadata.update(extra_metadata)
    return ContextPacket(
        session_id=manager.session_id,
        user_id=manager.user_id,
        goals=snapshot.goals,
        semantic_goals=snapshot.semantic_goals,
        turns=turns,
        latest_episode=snapshot.latest_episode,
        metadata=metadata,
    )


def format_turns(turns: Sequence[Dict[str, Any]]) -> str:
    """Format turns as a text string."""
    lines: List[str] = []
    for turn in turns:
        speaker = turn.get("speaker", "user")
        content = turn.get("content", "")
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines)


def default_metadata(packet: ContextPacket) -> Dict[str, Any]:
    """Extract default metadata from a context packet."""
    return {
        "session_id": packet.session_id,
        "user_id": packet.user_id,
        "goals": packet.goals,
        "semantic_goals": packet.semantic_goals,
        "latest_episode": packet.latest_episode,
    }


def render_context(packet: ContextPacket, include_turns: int = 6) -> str:
    """Return a text summary of the session for prompt conditioning."""

    explicit_goals = ", ".join(packet.goals) if packet.goals else "None captured"
    semantic = (
        ", ".join(packet.semantic_goals) if packet.semantic_goals else "None recorded"
    )
    latest_episode = packet.latest_episode or {}
    episode_text = (
        latest_episode.get("takeaways")
        or latest_episode.get("outcome")
        or "No reflections yet"
    )

    metadata_lines = [
        f"- {key}: {value}"
        for key, value in (packet.metadata or {}).items()
        if key not in {"clarification_state"}
    ]
    metadata_text = "\n".join(metadata_lines) if metadata_lines else "(no state metadata)"

    recent_turns = format_turns(packet.turns[-include_turns:]) or "(no prior turns)"

    return (
        f"Session ID: {packet.session_id}\n"
        f"User ID: {packet.user_id}\n"
        f"Explicit goals: {explicit_goals}\n"
        f"Semantic goals: {semantic}\n"
        f"Latest reflection: {episode_text}\n"
        f"State metadata:\n{metadata_text}\n"
        f"Recent conversation:\n{recent_turns}"
    )


def context_for(
    manager: SessionManager,
    include_turns: int = 8,
    extra_metadata: Dict[str, Any] | None = None,
) -> Tuple[ContextPacket, str]:
    """Build context packet and render it as text."""
    packet = build_context(
        manager, include_turns=include_turns, extra_metadata=extra_metadata
    )
    return packet, render_context(packet, include_turns=include_turns)


def values_context(
    manager: SessionManager,
    state: "ClarificationState | None",
    include_turns: int = 10,
) -> Tuple[ContextPacket, str]:
    """Build context for values clarification dialogue."""
    state_metadata = {
        "clarification_progress": {
            "turns": len(state.turns) if state else 0,
            "ready_for_products": state.ready_for_products if state else False,
        }
    }
    packet = build_context(
        manager, include_turns=include_turns, extra_metadata=state_metadata
    )
    return packet, render_context(packet, include_turns=include_turns)


__all__ = [
    "ContextPacket",
    "build_context",
    "format_turns",
    "default_metadata",
    "render_context",
    "context_for",
    "values_context",
]
