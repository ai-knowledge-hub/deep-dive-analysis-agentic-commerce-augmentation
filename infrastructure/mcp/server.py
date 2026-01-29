"""Lightweight MCP server that dispatches to discovery tooling."""

from __future__ import annotations

from typing import Callable, Dict

from infrastructure.mcp.tools import web_fetch, image_analyze, memory_write

TOOLS: Dict[str, Callable[..., dict]] = {
    "web_fetch": web_fetch.run,
    "image_analyze": image_analyze.run,
    "memory_write": memory_write.run,
}


def dispatch(tool_name: str, *args, **kwargs) -> dict:
    """Route a tool call to the appropriate handler."""
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS[tool_name](*args, **kwargs)


__all__ = ["dispatch"]
