"""Lightweight MCP server that dispatches to discovery tooling."""

from __future__ import annotations

from typing import Callable, Dict

from infrastructure.mcp.tools import (
    web_fetch,
    image_analyze,
    memory_write,
    product_search,
    serp_search,
)

TOOLS: Dict[str, Callable[..., dict]] = {
    "web_fetch": web_fetch.run,
    "image_analyze": image_analyze.run,
    "memory_write": memory_write.run,
    "product_search": product_search.run,
    "serp_search": serp_search.run,
}


def dispatch(tool_name: str, *args, **kwargs) -> dict:
    """Route a tool call to the appropriate handler."""
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS[tool_name](*args, **kwargs)


__all__ = ["dispatch"]
