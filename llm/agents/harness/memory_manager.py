from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from application.services.context_builder import (
    ContextPacket,
    context_for,
    goal_context,
)
from application.services.session_manager import SessionManager
from api.composition import default_deps


@dataclass(frozen=True)
class MemoryContext:
    packet: ContextPacket
    rendered: str


class MemoryManager:
    """Minimal memory adapter for the agent harness.

    Strangler approach:
    - In the short term, this wraps the existing `SessionManager` and
      `modules.conversation.context` helpers.
    - Over time, we can replace internals with repository interfaces without
      changing agent code.
    """

    def __init__(self) -> None:
        self._deps = default_deps()

    def session(
        self,
        *,
        user_id: str,
        client_id: str,
        session_id: str | None = None,
        brand_id: str | None = None,
        state: Optional[Dict[str, Any]] = None,
    ) -> SessionManager:
        return SessionManager(
            deps=self._deps,
            user_id=user_id,
            session_id=session_id,
            state=state or {},
            client_id=client_id,
            brand_id=brand_id,
        )

    def build_context(
        self,
        manager: SessionManager,
        *,
        include_turns: int = 8,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryContext:
        packet, rendered = context_for(
            manager, include_turns=include_turns, extra_metadata=extra_metadata
        )
        return MemoryContext(packet=packet, rendered=rendered)

    def build_goal_context(
        self,
        manager: SessionManager,
        *,
        goal_state: Any | None,
        include_turns: int = 10,
    ) -> MemoryContext:
        packet, rendered = goal_context(
            manager, state=goal_state, include_turns=include_turns
        )
        return MemoryContext(packet=packet, rendered=rendered)

    def extract_metadata(self, packet: ContextPacket) -> Dict[str, Any]:
        return {
            "session_id": packet.session_id,
            "user_id": packet.user_id,
            "goals": packet.goals,
            "semantic_goals": packet.semantic_goals,
            "latest_episode": packet.latest_episode,
        }
