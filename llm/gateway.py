"""Re-export from shared.llm.gateway for backward compatibility.

DEPRECATED: Import from shared.llm.gateway instead.
"""

from __future__ import annotations

from shared.llm.gateway import (
    chat,
    generate,
    generate_with_tools,
    get_llm_client,
    raw_client,
)

__all__ = [
    "chat",
    "generate",
    "generate_with_tools",
    "get_llm_client",
    "raw_client",
]
