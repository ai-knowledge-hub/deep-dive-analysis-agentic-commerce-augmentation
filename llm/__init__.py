"""Re-export from shared.llm for backward compatibility.

DEPRECATED: Import from shared.llm instead.
"""

from __future__ import annotations

from shared.llm import (
    chat,
    generate,
    generate_with_tools,
    get_llm_client,
    raw_client,
)

__all__ = [
    "prompts",
    "tools",
    "get_llm_client",
    "generate",
    "chat",
    "generate_with_tools",
    "raw_client",
]
