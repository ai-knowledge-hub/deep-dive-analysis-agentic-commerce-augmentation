"""Re-export from shared.llm.clients for backward compatibility.

DEPRECATED: Import from shared.llm.clients instead.
"""

from __future__ import annotations

from shared.llm.clients import LLMClient, get_llm_client

__all__ = [
    "LLMClient",
    "get_llm_client",
]
