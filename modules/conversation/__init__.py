"""Conversation module - orchestration of conversation flow."""

from modules.conversation.context import (
    ContextPacket,
    build_context,
    format_turns,
    default_metadata,
    render_context,
    context_for,
    values_context,
)
from modules.conversation.guards import AutonomyGuardAgent
from modules.conversation.agents import (
    IntentAgent,
    CommerceAgent,
    ReflectionAgent,
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
    "values_context",
    # Guards
    "AutonomyGuardAgent",
    # Agents
    "IntentAgent",
    "CommerceAgent",
    "ReflectionAgent",
    "ExplainAgent",
    "CapabilityAgent",
    "run_research",
]
