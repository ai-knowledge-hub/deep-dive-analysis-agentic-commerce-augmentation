"""Backward compatibility: conversation context helpers.

Historically these lived under `modules.conversation.context`.
Canonical paths:
- Pure types + formatting: `domain.conversation.context`
- SessionManager wiring: `application.services.context_builder`
"""

from application.services.context_builder import (
    build_context,
    context_for,
    goal_context,
)
from domain.conversation.context import (
    ContextPacket,
    default_metadata,
    format_turns,
    render_context,
)

__all__ = [
    "ContextPacket",
    "build_context",
    "context_for",
    "default_metadata",
    "format_turns",
    "render_context",
    "goal_context",
]
