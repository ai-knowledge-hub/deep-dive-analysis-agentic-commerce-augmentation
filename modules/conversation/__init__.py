"""Conversation module - orchestration of conversation flow."""

from modules.conversation.context import (
    ContextPacket,
    build_context,
    format_turns,
    default_metadata,
    render_context,
    context_for,
    goal_context,
)
from modules.conversation.agents import (
    IntentAgent,
    CommerceAgent,
    ExplainAgent,
    CapabilityAgent,
)
from modules.conversation.research import run_research

__all__ = [
    # Context
    "ContextPacket",
    "build_context",
    "format_turns",
    "default_metadata",
    "render_context",
    "context_for",
    "goal_context",
    # Agents
    "IntentAgent",
    "CommerceAgent",
    "ExplainAgent",
    "CapabilityAgent",
    "run_research",
]
