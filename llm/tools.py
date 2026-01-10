"""Model-agnostic function calling tool definitions."""

from __future__ import annotations

from typing import Any

from modules.mcp.server import dispatch

# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

PRODUCT_SEARCH_TOOL = {
    "name": "product_search",
    "description": (
        "Search for products that enable specific capabilities or serve user goals. "
        "Use this when you need to find products that match user needs. "
        "Returns products with confidence scores and source attribution."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": (
                    "The capability, goal, or need to search for. "
                    "Examples: 'reduce back pain', 'productivity tools', 'ergonomic workspace'"
                ),
            },
        },
        "required": ["query"],
    },
}


PRODUCT_COMPARE_TOOL = {
    "name": "product_compare",
    "description": (
        "Compare multiple products side-by-side on empowerment dimensions. "
        "Use this to help users understand tradeoffs between options. "
        "Requires product IDs from a previous search."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "product_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of product IDs to compare (2-4 products recommended)",
            },
        },
        "required": ["product_ids"],
    },
}


ASSESS_EMPOWERMENT_TOOL = {
    "name": "assess_empowerment",
    "description": (
        "Assess how well a set of products aligns with the user's stated goals. "
        "Returns alignment scores and identifies which goals are served vs not served. "
        "Use this before presenting recommendations to ensure empowerment focus."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goals": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of user's stated goals (from values clarification)",
            },
            "product_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "List of product IDs to assess",
            },
        },
        "required": ["goals", "product_ids"],
    },
}


GENERATE_REFLECTION_TOOL = {
    "name": "generate_reflection",
    "description": (
        "Generate a reflection on the shopping conversation. "
        "Use this at the end of a conversation to help the user "
        "internalize insights about their goals and decisions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "entries": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Key points from the conversation to reflect on. "
                    "Include: goals identified, products considered, decision made"
                ),
            },
        },
        "required": ["entries"],
    },
}


ALL_TOOLS = [
    PRODUCT_SEARCH_TOOL,
    PRODUCT_COMPARE_TOOL,
    ASSESS_EMPOWERMENT_TOOL,
    GENERATE_REFLECTION_TOOL,
]


# =============================================================================
# TOOL EXECUTION
# =============================================================================


def execute_tool(name: str, args: dict[str, Any]) -> dict:
    """Execute a tool by name with the given arguments."""
    tool_mapping = {
        "product_search": ("product_search", lambda a: (a["query"],)),
        "product_compare": ("product_compare", lambda a: (a["product_ids"],)),
        "assess_empowerment": (
            "assess_empowerment",
            lambda a: (a["goals"], a["product_ids"]),
        ),
        "generate_reflection": ("generate_reflection", lambda a: (a["entries"],)),
    }

    if name not in tool_mapping:
        return {"error": f"Unknown tool: {name}"}

    mcp_name, arg_mapper = tool_mapping[name]

    try:
        mcp_args = arg_mapper(args)
        return dispatch(mcp_name, *mcp_args)
    except Exception as exc:  # pragma: no cover - MCP dispatch may raise
        return {"error": str(exc)}


def get_tool_by_name(name: str) -> dict | None:
    for tool in ALL_TOOLS:
        if tool["name"] == name:
            return tool
    return None


def get_function_declarations() -> list[dict]:
    """Return the tools in the format expected by modern LLM SDKs."""
    return [
        {
            "function_declarations": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                }
                for tool in ALL_TOOLS
            ]
        }
    ]


def get_llm_tools() -> list[dict]:
    """Alias for backwards compatibility."""
    return get_function_declarations()
