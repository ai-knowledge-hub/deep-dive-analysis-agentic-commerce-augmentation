"""Build conversation context packets from SessionManager snapshots."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Tuple

from domain.conversation.context import ContextPacket, render_context
from application.services.conversation.session_manager import SessionManager

if TYPE_CHECKING:  # pragma: no cover
    from domain.values.types import GoalClarificationState


def build_context(
    manager: SessionManager,
    *,
    include_turns: int = 8,
    extra_metadata: Dict[str, Any] | None = None,
) -> ContextPacket:
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


def context_for(
    manager: SessionManager,
    *,
    include_turns: int = 8,
    extra_metadata: Dict[str, Any] | None = None,
) -> Tuple[ContextPacket, str]:
    packet = build_context(
        manager, include_turns=include_turns, extra_metadata=extra_metadata
    )
    return packet, render_context(packet, include_turns=include_turns)


def goal_context(
    manager: SessionManager,
    *,
    state: "GoalClarificationState | None",
    include_turns: int = 10,
) -> Tuple[ContextPacket, str]:
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


__all__ = ["ContextPacket", "build_context", "context_for", "goal_context"]
