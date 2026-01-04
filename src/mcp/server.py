"""Placeholder MCP server hosting the tool surface."""

from __future__ import annotations

from typing import Callable, Dict

from src.mcp.tools import assess_empowerment, compare, generate_reflection, search

TOOLS: Dict[str, Callable[..., dict]] = {
    "product_search": search.run,
    "product_compare": compare.run,
    "assess_empowerment": assess_empowerment.run,
    "generate_reflection": generate_reflection.run,
}


def dispatch(tool_name: str, *args, **kwargs) -> dict:
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS[tool_name](*args, **kwargs)
