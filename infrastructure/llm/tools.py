"""Model-agnostic function calling tool definitions + execution."""

from __future__ import annotations

from typing import Any, Dict, List

from infrastructure.mcp.server import dispatch


WEB_FETCH_TOOL = {
    "name": "web_fetch",
    "description": (
        "Fetch a web page from an allowlisted host for research/verification. "
        "Returns truncated text with content type metadata."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "HTTP/HTTPS URL to fetch (must be on allowlist).",
            },
            "max_chars": {
                "type": "integer",
                "description": "Max characters to return (default 5000).",
            },
        },
        "required": ["url"],
    },
}

IMAGE_ANALYZE_TOOL = {
    "name": "image_analyze",
    "description": "Analyze an image for product-relevant attributes (stub until vision is wired).",
    "parameters": {
        "type": "object",
        "properties": {
            "image_url": {"type": "string", "description": "Public URL to the image."},
            "image_base64": {
                "type": "string",
                "description": "Base64-encoded image data.",
            },
        },
        "required": [],
    },
}

MEMORY_WRITE_TOOL = {
    "name": "memory_write",
    "description": "Write entries to semantic memory with consent-aware controls.",
    "parameters": {
        "type": "object",
        "properties": {
            "key": {
                "type": "string",
                "description": "Semantic memory key (e.g., goals).",
            },
            "value": {"type": "string", "description": "Single value to append."},
            "values": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Values to set when mode='set'.",
            },
            "mode": {
                "type": "string",
                "description": "Write mode: append or set.",
                "enum": ["append", "set"],
            },
        },
        "required": ["key"],
    },
}

PRODUCT_SEARCH_TOOL = {
    "name": "product_search",
    "description": (
        "Search the web for product pages using a query and return top URLs."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query string."},
            "limit": {
                "type": "integer",
                "description": "Max number of result URLs (default 5).",
            },
        },
        "required": ["query"],
    },
}

SERP_SEARCH_TOOL = {
    "name": "serp_search",
    "description": "Search Google via SerpAPI and return top organic result URLs.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query string."},
            "location": {
                "type": "string",
                "description": "Optional location string (e.g., 'Austin, Texas, United States').",
            },
            "gl": {"type": "string", "description": "Country code (e.g., us)."},
            "hl": {"type": "string", "description": "Language code (e.g., en)."},
            "limit": {
                "type": "integer",
                "description": "Max number of result URLs (default 5).",
            },
        },
        "required": ["query"],
    },
}

ALL_TOOLS = [
    WEB_FETCH_TOOL,
    IMAGE_ANALYZE_TOOL,
    MEMORY_WRITE_TOOL,
    PRODUCT_SEARCH_TOOL,
    SERP_SEARCH_TOOL,
]


def execute_tool(name: str, args: Dict[str, Any]) -> dict:
    """Execute a tool by name with the given arguments."""
    tool_mapping = {
        "web_fetch": ("web_fetch", lambda a: (a["url"], a.get("max_chars", 5000))),
        "image_analyze": (
            "image_analyze",
            lambda a: (a.get("image_url"), a.get("image_base64")),
        ),
        "memory_write": (
            "memory_write",
            lambda a: (
                a["key"],
                a.get("values"),
                a.get("value"),
                a.get("mode", "append"),
            ),
        ),
        "product_search": (
            "product_search",
            lambda a: (a["query"], a.get("limit", 5)),
        ),
        "serp_search": (
            "serp_search",
            lambda a: (
                a["query"],
                a.get("location"),
                a.get("gl"),
                a.get("hl"),
                a.get("limit", 5),
            ),
        ),
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


def llm_schema() -> List[dict]:
    return get_llm_tools()


__all__ = [
    "llm_schema",
    "execute_tool",
    "get_llm_tools",
    "get_tool_by_name",
    "get_function_declarations",
]
