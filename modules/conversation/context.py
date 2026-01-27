"""Compatibility shim for conversation context helpers.

Canonical pure types live in `domain.conversation.context`.
SessionManager-dependent builders live in `application.services.context_builder`.
"""

from __future__ import annotations

from application.services.context_builder import build_context, context_for, goal_context
from domain.conversation.context import ContextPacket, default_metadata, format_turns, render_context


__all__ = [
    "ContextPacket",
    "build_context",
    "format_turns",
    "default_metadata",
    "render_context",
    "context_for",
    "goal_context",
]
